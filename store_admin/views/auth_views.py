from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')

    if request.method == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")
        # Get 'next' from POST or GET to ensure it persists through the form submission
        next_url = request.POST.get('next') or request.GET.get('next')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.name}!")

            # 2. HANDLE REDIRECT LOGIC
            if next_url:
                return redirect(next_url)
            return redirect('/dashboard/')

        else:
            messages.error(request, "Invalid username or password")
            return render(request, 'sbadmin/pages/login.html', {'error': 'Invalid username or password'})

    return render(request, 'sbadmin/pages/login.html')

@login_required
def logout_view(request):
    for key in list(request.session.keys()):
        del request.session[key]
    logout(request)
    request.session.flush()
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')