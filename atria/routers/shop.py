"""Shop and Creator Marketplace router for Atria."""

from decimal import Decimal
from typing import Any, List, Optional

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from ninja import Router, Schema
from ninja.errors import HttpError
from shipping.models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    Subscription,
    SubscriptionTier,
)

shop_router = Router()


class ProductOut(Schema):
    id: int
    name: str
    slug: str
    description: str
    price: str
    sku: str
    creator_username: Optional[str] = None
    category_name: Optional[str] = None
    available: bool


class ProductIn(Schema):
    name: str
    price: str
    sku: str
    description: str = ""
    category_id: Optional[int] = None


class CartItemIn(Schema):
    product_id: int
    quantity: int = 1


class CartItemOut(Schema):
    id: int
    product_id: int
    product_name: str
    price: str
    quantity: int
    subtotal: str


class CartOut(Schema):
    id: int
    total: str
    items: List[CartItemOut]


class OrderOut(Schema):
    id: int
    status: str
    total: str
    created: str
    items_count: int


class TierIn(Schema):
    name: str
    slug: Optional[str] = None
    price: str
    currency: str = "USD"
    billing_frequency: str = "monthly"
    description: str = ""
    perks: List[str] = []


class TierOut(Schema):
    id: int
    name: str
    slug: str
    price: str
    currency: str
    billing_frequency: str
    description: str
    perks: List[Any]
    is_active: bool


class SubscriptionOut(Schema):
    id: int
    tier_name: str
    creator_username: str
    status: str
    payment_rail: str
    current_period_end: Optional[str] = None


def get_or_create_cart(request) -> Cart:
    """Retrieves or creates a cart instance based on user session or authentication."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    if not request.session.session_key:
        request.session.save()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


@shop_router.get("/products", response=List[ProductOut])
def list_products(
    request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Lists available products in the marketplace."""
    qs = Product.objects.filter(available=True).select_related("creator", "category")
    if search:
        qs = qs.filter(name__icontains=search)
    if category:
        qs = qs.filter(category__slug=category)

    products = qs[offset : offset + limit]
    return [
        {
            "id": p.pk,
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "price": str(p.price),
            "sku": p.sku,
            "creator_username": p.creator.username if p.creator else None,
            "category_name": p.category.name if p.category else None,
            "available": p.available,
        }
        for p in products
    ]


@shop_router.get("/products/{id}", response=ProductOut)
def get_product(request, id: int):
    """Retrieves details of a specific product."""
    p = get_object_or_404(Product.objects.select_related("creator", "category"), pk=id)
    return {
        "id": p.pk,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "price": str(p.price),
        "sku": p.sku,
        "creator_username": p.creator.username if p.creator else None,
        "category_name": p.category.name if p.category else None,
        "available": p.available,
    }


@shop_router.post("/products", response=ProductOut)
def create_product(request, payload: ProductIn):
    """Creates a new product listing in the marketplace."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required to create products")

    category = None
    if payload.category_id:
        category = Category.objects.filter(pk=payload.category_id).first()

    slug_base = slugify(payload.name) or "product"
    slug = slug_base
    counter = 1
    while Product.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{counter}"
        counter += 1

    product = Product.objects.create(
        name=payload.name,
        slug=slug,
        description=payload.description,
        price=Decimal(payload.price),
        sku=payload.sku,
        creator=request.user,
        category=category,
        available=True,
    )
    return {
        "id": product.pk,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price": str(product.price),
        "sku": product.sku,
        "creator_username": request.user.username,
        "category_name": category.name if category else None,
        "available": product.available,
    }


@shop_router.get("/cart", response=CartOut)
def get_cart(request):
    """Retrieves the current shopping cart and items."""
    cart = get_or_create_cart(request)
    items = cart.items.select_related("product").all()
    return {
        "id": cart.pk,
        "total": str(cart.total()),
        "items": [
            {
                "id": it.pk,
                "product_id": it.product.pk,
                "product_name": it.product.name,
                "price": str(it.product.price),
                "quantity": it.quantity,
                "subtotal": str(it.subtotal()),
            }
            for it in items
        ],
    }


@shop_router.post("/cart/items", response=CartOut)
def add_cart_item(request, payload: CartItemIn):
    """Adds a product to the user's active cart."""
    product = get_object_or_404(Product, pk=payload.product_id, available=True)
    cart = get_or_create_cart(request)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": payload.quantity},
    )
    if not created:
        item.quantity += payload.quantity
        item.save()

    items = cart.items.select_related("product").all()
    return {
        "id": cart.pk,
        "total": str(cart.total()),
        "items": [
            {
                "id": it.pk,
                "product_id": it.product.pk,
                "product_name": it.product.name,
                "price": str(it.product.price),
                "quantity": it.quantity,
                "subtotal": str(it.subtotal()),
            }
            for it in items
        ],
    }


@shop_router.delete("/cart/items/{item_id}", response=CartOut)
def remove_cart_item(request, item_id: int):
    """Removes an item from the current cart."""
    cart = get_or_create_cart(request)
    CartItem.objects.filter(cart=cart, pk=item_id).delete()

    items = cart.items.select_related("product").all()
    return {
        "id": cart.pk,
        "total": str(cart.total()),
        "items": [
            {
                "id": it.pk,
                "product_id": it.product.pk,
                "product_name": it.product.name,
                "price": str(it.product.price),
                "quantity": it.quantity,
                "subtotal": str(it.subtotal()),
            }
            for it in items
        ],
    }


@shop_router.get("/orders", response=List[OrderOut])
def list_orders(request):
    """Lists orders placed by the authenticated user."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required to view orders")

    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created")
    )
    return [
        {
            "id": o.pk,
            "status": o.status,
            "total": str(o.total),
            "created": o.created.isoformat(),
            "items_count": o.items.count(),
        }
        for o in orders
    ]


@shop_router.post("/orders", response=OrderOut)
def create_order_from_cart(request):
    """Creates a new Order from the items in the current shopping cart."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required to place an order")

    cart = get_or_create_cart(request)
    items = list(cart.items.select_related("product").all())
    if not items:
        raise HttpError(400, "Cannot checkout an empty cart")

    order = Order.objects.create(
        user=request.user,
        total=cart.total(),
        status=Order.STATUS_PENDING,
    )
    for it in items:
        OrderItem.objects.create(
            order=order,
            product=it.product,
            quantity=it.quantity,
            price=it.product.price,
        )

    # Clear cart items after checkout
    cart.items.all().delete()

    return {
        "id": order.pk,
        "status": order.status,
        "total": str(order.total),
        "created": order.created.isoformat(),
        "items_count": len(items),
    }


@shop_router.get("/creators/{creator_id}/tiers", response=List[TierOut])
def get_creator_tiers(request, creator_id: int):
    """Lists subscription tiers offered by a creator."""
    creator = get_object_or_404(User, pk=creator_id)
    tiers = SubscriptionTier.objects.filter(creator=creator, is_active=True)
    return [
        {
            "id": t.pk,
            "name": t.name,
            "slug": t.slug,
            "price": str(t.price),
            "currency": t.currency,
            "billing_frequency": t.billing_frequency,
            "description": t.description,
            "perks": t.perks,
            "is_active": t.is_active,
        }
        for t in tiers
    ]


@shop_router.post("/creators/{creator_id}/tiers", response=TierOut)
def create_creator_tier(request, creator_id: int, payload: TierIn):
    """Creates a new membership tier for a creator."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")
    if request.user.pk != creator_id:
        raise HttpError(403, "Cannot create tiers for other creators")

    slug = payload.slug or slugify(payload.name)
    tier = SubscriptionTier.objects.create(
        creator=request.user,
        name=payload.name,
        slug=slug,
        price=Decimal(payload.price),
        currency=payload.currency,
        billing_frequency=payload.billing_frequency,
        description=payload.description,
        perks=payload.perks,
        is_active=True,
    )
    return {
        "id": tier.pk,
        "name": tier.name,
        "slug": tier.slug,
        "price": str(tier.price),
        "currency": tier.currency,
        "billing_frequency": tier.billing_frequency,
        "description": tier.description,
        "perks": tier.perks,
        "is_active": tier.is_active,
    }


@shop_router.get("/subscriptions", response=List[SubscriptionOut])
def list_subscriptions(request):
    """Lists active creator subscriptions of the authenticated user."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required to view subscriptions")

    subs = (
        Subscription.objects.filter(subscriber=request.user)
        .select_related("tier", "tier__creator")
        .order_by("-created")
    )
    return [
        {
            "id": s.pk,
            "tier_name": s.tier.name,
            "creator_username": s.tier.creator.username,
            "status": s.status,
            "payment_rail": s.payment_rail,
            "current_period_end": (
                s.current_period_end.isoformat() if s.current_period_end else None
            ),
        }
        for s in subs
    ]
