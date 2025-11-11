from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def add_new_vendor(request):
    return render(request, 'sbadmin/pages/vendor/add_new.html', {'user': request.user})

@login_required
def all_vendors(request):
    return render(request, 'sbadmin/pages/vendor/all_listing.html', {'user': request.user})

