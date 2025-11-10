from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def test(request):
    return HttpResponse("Hi Testing install")
# Create your views here.

def login_view(request):
    if request.method  == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "You are now logged in")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password")
            return render(request, 'sbadmin/pages/login.html', {'error':'Invalid username or password'})
        
    return render(request, 'sbadmin/pages/login.html')
    #return HttpResponse("Hi Testing install")

@login_required
def dashboard(request):
    return render(request, 'sbadmin/pages/index.html', {'user': request.user})


def logout_view(request):
    return redirect('login')