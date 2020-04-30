from django.db.models import *
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
import json

locale = json.load(open('settings.json'))['locale_date']

def user(name): return User.objects.filter(username=name)[0]
def superuser(): return User.objects.filter(is_superuser=True)[0]

class Profile(Model):
    user = OneToOneField(User, on_delete=CASCADE)
    coins = IntegerField(default=0)
    visual = CharField(default="",max_length=100)
    career = CharField(default='',max_length=50)
    birthday = DateTimeField(default=timezone.now)
    google_token = TextField(default="",max_length=120)
    twitter_token = TextField(default="",max_length=120)
    facebook_token = TextField(default="",max_length=120)
    bio = TextField(default='',max_length=140)
    interface = IntegerField(default=1)
    typeditor = IntegerField(default=1)
    monetize = IntegerField(default=0)
    language = IntegerField(default=0)
    date = DateTimeField(default=timezone.now)
    def years_old(self): return datetime.timedelta(self.birthday,date.today)
    def token(self): return ''
    def get_username(self): return self.user.username
    def month(self): return locale[self.date.month-1]
    
class Place(Model):
    name = CharField(default="",max_length=50)
    user = OneToOneField(User, on_delete=CASCADE)
    code = CharField(default="",max_length=100)
    city = CharField(default="",max_length=100)
    country = CharField(default="",max_length=50)
    date = DateTimeField(default=timezone.now)

class Followed(Model):
    followed = IntegerField(default=1)
    follower = IntegerField(default=2)
    date = DateTimeField()

class Page(Model):
    name = CharField(default='!#',max_length=50)
    content = TextField(default='')
    user = ForeignKey(User,related_name='+', on_delete=CASCADE)
    date = DateTimeField()
    def token(self): return self.name[:2]
    def name_trimmed(self): return self.name[2:]
    def month(self): return locale[self.date.month-1]
    
class Basket(Model):
    name = CharField(default='++',max_length=2)
    user = ForeignKey(User,related_name='+', on_delete=CASCADE)
    deliverable = BooleanField(default=False)
    product = IntegerField(default=1)
    date = DateTimeField()
    def token(self): return self.name[:2]
    # def total_value(self): return self.quantity*self.product.credit
    # def product_trimmed(self): return self.product.name_trimmed()
    # def product_month(self): return self.product.real_month()

class Sellable(Model):
    name = CharField(default='$$',max_length=100)
    user = ForeignKey(User,related_name='+', on_delete=CASCADE)
    paid = BooleanField(default=False)
    returnable = BooleanField(default=False)
    value = FloatField(default=1.00)
    visual = CharField(default='',max_length=150)
    sellid = IntegerField(default=1)
    date = DateTimeField(default=timezone.now)
    def token(self): return '$$'
    def name_trimmed(self): return self.name
    def type_object(self): return self.name[:2]
 
class Deliverable(Model):
    name = CharField(default='((',max_length=50)
    user = ForeignKey(User,related_name='+', on_delete=CASCADE)
    product = ForeignKey(Sellable,related_name='+', on_delete=CASCADE)
    mail_code = CharField(default='',max_length=100)
    height = IntegerField(default=1)
    length = IntegerField(default=1)
    width = IntegerField(default=1)
    weight = IntegerField(default=10)
    value = FloatField(default=0.0)
    date = DateTimeField(default=timezone.now)
    def token(self): return self.name[:2]
    def name_trimmed(self): return self.name.split(';')[0][1:]
    def month(self): return locale[self.date.month-1]
    
Profile.year = property(lambda p: p.years_old())
Profile.name = property(lambda p: p.get_username())
User.profile = property(lambda u: Profile.objects.get_or_create(user=u)[0])
User.place = property(lambda p: Place.objects.get_or_create(user=p)[0])
