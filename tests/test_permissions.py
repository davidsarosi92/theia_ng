"""The access gate + the migrate-created ``theia_ng.access`` permission."""

from django.contrib.auth.models import Permission, User
from django.test import RequestFactory

from theia_ng.permissions import has_access


def test_access_permission_is_created_by_migration(db):
    perm = Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    assert perm.name == "Can access the Theia NG admin"


def test_has_access_enforces_the_permission(db):
    user = User.objects.create_user("staff", password="x")
    req = RequestFactory().get("/theia/")
    req.user = user
    assert has_access(req) is False  # no permission yet

    perm = Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    user.user_permissions.add(perm)
    # reload to bypass the per-instance permission cache
    req.user = User.objects.get(pk=user.pk)
    assert has_access(req) is True


def test_superuser_bypasses_the_gate(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    req = RequestFactory().get("/theia/")
    req.user = user
    assert has_access(req) is True
