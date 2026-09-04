from django.contrib import admin
from .models import CustomUser,SellerProfile
# Register your models here.
admin.site.register(CustomUser)
admin.site.register(SellerProfile)