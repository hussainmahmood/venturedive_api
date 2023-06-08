from django.urls import path, include

from .views import UrlView, IconView, FieldView, FunctionView, ViewView, CompanyView, UserGroupView, UserView, LoginView


urlpatterns = [
    path('url/', UrlView.as_view(), name="url-list"),
    path('url/<int:pk>', UrlView.as_view(), name="url-detail"),

    path('icon/', IconView.as_view(), name="icon-list"),
    path('icon/<int:pk>', IconView.as_view(), name="icon-detail"),

    path('field/', FieldView.as_view(), name="field-list"),
    path('field/<int:pk>', FieldView.as_view(), name="field-detail"),

    path('function/', FunctionView.as_view(), name="function-list"),
    path('function/<int:pk>', FunctionView.as_view(), name="function-detail"),

    path('view/', ViewView.as_view(), name="view-list"),
    path('view/<int:pk>', ViewView.as_view(), name="view-detail"),

    path('companies/', CompanyView.as_view(), name="company-list"),
    path('companies/<int:pk>', CompanyView.as_view(), name="company-detail"),

    path('usergroups/', UserGroupView.as_view(), name="user-group-list"),
    path('usergroups/<int:pk>', UserGroupView.as_view(), name="user-group-detail"),

    path('users/', UserView.as_view(), name="user-list"),
    path('users/<int:pk>', UserView.as_view(), name="user-detail"),

    path('login/', LoginView.as_view(), name="login"),
]
