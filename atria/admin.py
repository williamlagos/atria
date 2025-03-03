from django.contrib import admin
from socialize.socialize.models import *
from plethora.plethora.models import *
from shipping.shipping.models import *
from emporio.emporio.models import *
from feedly.feedly.models import *

class ContentsAdminSite(admin.AdminSite):

    site_header = 'Dashboard'
    site_title = 'Contents'
    index_title = 'Site Administration'

dashboard = ContentsAdminSite(name='myadmin')
dashboard.register(Profile)
dashboard.register(Product)
dashboard.register(Basket)
dashboard.register(Order)
dashboard.register(Page)
dashboard.register(Showable)
dashboard.register(Spreadable)
dashboard.register(Deliverable)