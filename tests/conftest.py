import pytest
from api.models import Student, Group, UserProfile
from django.contrib.auth.models import User

@pytest.fixture(autouse=True)
def student1(db, group1):
    return Student.objects.create(
        first_name="Louis",
        last_name="Daguerre",
        email="louis.daguerre@example.com",
        matriculation_number="1234367890",
        course="Biology",
        semester=1,
        group=group1,
    )

@pytest.fixture(autouse=True)
def student2(db, group2):
    return Student.objects.create(
        first_name="John",
        last_name="Herschel",
        email="saturn@example.com",
        matriculation_number="1334367890",
        course="Chemistry",
        semester=1,
        group=group2,
    )

@pytest.fixture(autouse=True)
def group1(db):
    return Group.objects.create(
        name="A",
        description="Group 1 description",
    )

@pytest.fixture(autouse=True)
def group2(db):
    return Group.objects.create(
        name="B",
        description="Group 2 description",
    )

@pytest.fixture(autouse=True)
def user1(db, group1):
    user = User.objects.create_user(
        username="alfred",
        email="alfred@example.com",
        password="password",
    )
    UserProfile.objects.create(user=user, group=group1)
    return user

@pytest.fixture(autouse=True)
def superuser(db):
    user = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password",
    )
    return user

@pytest.fixture
def logged_in_client_superuser(client, superuser):
    client.force_login(superuser)
    return client

@pytest.fixture
def logged_in_client1(client, user1):
    client.force_login(user1)
    return client