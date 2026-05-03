import pytest


# Make sure that the user can only see the students in their group
def test_protected_model_access(logged_in_client1):
    response = logged_in_client1.get("/api/students/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["group"]["name"] == "A"


# Make sure that the superuser can see all the students
def test_protected_model_access_superuser(logged_in_client_superuser):
    response = logged_in_client_superuser.get("/api/students/")
    assert response.status_code == 200
    assert len(response.data) == 2
    assert response.data[0]["group"]["name"] == "A"
    assert response.data[1]["group"]["name"] == "B"
