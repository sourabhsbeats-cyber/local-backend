from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Create your views here.
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = request.GET.get('next')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.is_superuser:

                print(next_url)
                if next_url:
                    return redirect(next_url)

                return redirect('/dashboard/')
            else:
                return redirect(request.GET.get('next', '/dashboard'))

            messages.success(request, "You are now logged in")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password")
            return render(request, 'sbadmin/pages/login.html', {'error': 'Invalid username or password'})

    return render(request, 'sbadmin/pages/login.html')
    # return HttpResponse("Hi Testing install")

@login_required
def logout_view(request):
    for key in list(request.session.keys()):
        del request.session[key]
    logout(request)
    request.session.flush()
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')