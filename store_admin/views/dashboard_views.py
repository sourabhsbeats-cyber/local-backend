from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
def dashboard(request):
    return render(request, 'sbadmin/pages/dashboard.html', {'user': request.user})

