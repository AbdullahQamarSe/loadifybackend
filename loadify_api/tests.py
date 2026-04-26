from django.test import TestCase
from rest_framework.test import APIClient

from .models import Load, Truck, User


class LoadCapacityRulesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.driver = User.objects.create_user(
            username="driver1",
            email="driver@example.com",
            password="testpass123",
            role="driver",
        )
        self.trader = User.objects.create_user(
            username="trader1",
            email="trader@example.com",
            password="testpass123",
            role="trader",
        )
        self.truck = Truck.objects.create(
            driver=self.driver,
            truck_type="Mazda",
            registration_no="ABC-123",
            total_capacity="1000.00",
            available_capacity="1000.00",
        )

    def create_load(self, weight, load_mode="Partial", status="Pending"):
        return Load.objects.create(
            user=self.trader,
            pickup_location="Karachi",
            drop_location="Lahore",
            weight=weight,
            load_type="Normal",
            load_mode=load_mode,
            budget_rate="100.00",
            status=status,
        )

    def test_driver_cannot_accept_load_heavier_than_truck_capacity(self):
        first_load = self.create_load("500.00", load_mode="Partial")
        second_load = self.create_load("1001.00", load_mode="Partial")

        first_response = self.client.post(
            f"/api/loads/{first_load.id}/accept",
            {"driver_id": self.driver.id},
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            f"/api/loads/{second_load.id}/accept",
            {"driver_id": self.driver.id},
            format="json",
        )
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            second_response.json()["error"],
            "Entered load exceeds available truck capacity",
        )

        self.truck.refresh_from_db()
        self.assertEqual(str(self.truck.available_capacity), "500.00")

    def test_driver_with_active_loads_still_sees_any_request_that_fits_truck_capacity(self):
        accepted_partial = self.create_load("500.00", load_mode="Partial")
        fitting_partial = self.create_load("500.00", load_mode="Partial")
        heavy_partial = self.create_load("1200.00", load_mode="Partial")
        full_load = self.create_load("400.00", load_mode="Full")

        accepted_partial.driver = self.driver
        accepted_partial.truck = self.truck
        accepted_partial.status = "Accepted"
        accepted_partial.save()

        response = self.client.get(f"/api/loads/pending?driver_id={self.driver.id}")

        self.assertEqual(response.status_code, 200)
        response_ids = {item["id"] for item in response.json()}
        self.assertIn(fitting_partial.id, response_ids)
        self.assertIn(full_load.id, response_ids)
        self.assertNotIn(heavy_partial.id, response_ids)

    def test_driver_with_active_full_load_can_still_see_and_accept_other_loads(self):
        full_load = self.create_load("800.00", load_mode="Full")
        other_partial = self.create_load("200.00", load_mode="Partial")

        full_load.driver = self.driver
        full_load.truck = self.truck
        full_load.status = "Accepted"
        full_load.save()

        response = self.client.get(f"/api/loads/pending?driver_id={self.driver.id}")

        self.assertEqual(response.status_code, 200)
        response_ids = {item["id"] for item in response.json()}
        self.assertIn(other_partial.id, response_ids)

        accept_response = self.client.post(
            f"/api/loads/{other_partial.id}/accept",
            {"driver_id": self.driver.id},
            format="json",
        )
        self.assertEqual(accept_response.status_code, 200)

    def test_increasing_total_capacity_does_not_override_remaining_partial_capacity(self):
        accepted_partial = self.create_load("500.00", load_mode="Partial")
        hidden_heavier_partial = self.create_load("1200.00", load_mode="Partial")

        accepted_partial.driver = self.driver
        accepted_partial.truck = self.truck
        accepted_partial.status = "Accepted"
        accepted_partial.save()

        self.truck.available_capacity = "500.00"
        self.truck.save(update_fields=["available_capacity"])

        self.truck.total_capacity = "1500.00"
        self.truck.save(update_fields=["total_capacity"])

        response = self.client.get(f"/api/loads/pending?driver_id={self.driver.id}")

        self.assertEqual(response.status_code, 200)
        response_ids = {item["id"] for item in response.json()}
        self.assertNotIn(hidden_heavier_partial.id, response_ids)

        self.truck.refresh_from_db()
        self.assertEqual(str(self.truck.available_capacity), "500.00")

    def test_current_driver_loads_returns_accepted_and_picked_loads(self):
        accepted_load = self.create_load("300.00", load_mode="Partial", status="Accepted")
        accepted_load.driver = self.driver
        accepted_load.truck = self.truck
        accepted_load.save()

        picked_load = self.create_load("200.00", load_mode="Partial", status="Picked")
        picked_load.driver = self.driver
        picked_load.truck = self.truck
        picked_load.save()

        response = self.client.get(f"/api/loads/current?driver_id={self.driver.id}")

        self.assertEqual(response.status_code, 200)
        response_ids = {item["id"] for item in response.json()}
        self.assertIn(accepted_load.id, response_ids)
        self.assertIn(picked_load.id, response_ids)

    def test_pickup_endpoint_marks_load_as_picked(self):
        load = self.create_load("250.00", load_mode="Partial", status="Accepted")
        load.driver = self.driver
        load.truck = self.truck
        load.save()

        response = self.client.post(
            f"/api/loads/{load.id}/pickup",
            {"driver_id": self.driver.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        load.refresh_from_db()
        self.assertEqual(load.status, "Picked")

    def test_location_update_saves_driver_live_coordinates(self):
        load = self.create_load("250.00", load_mode="Partial", status="Picked")
        load.driver = self.driver
        load.truck = self.truck
        load.save()

        response = self.client.post(
            f"/api/loads/{load.id}/location",
            {
                "driver_id": self.driver.id,
                "latitude": "24.8607000",
                "longitude": "67.0011000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        load.refresh_from_db()
        self.assertEqual(str(load.driver_current_latitude), "24.8607000")
        self.assertEqual(str(load.driver_current_longitude), "67.0011000")
        self.assertIsNotNone(load.driver_location_updated_at)

    def test_complete_endpoint_marks_picked_load_as_completed(self):
        load = self.create_load("250.00", load_mode="Partial", status="Picked")
        load.driver = self.driver
        load.truck = self.truck
        load.save()

        self.truck.available_capacity = "750.00"
        self.truck.save(update_fields=["available_capacity"])

        response = self.client.post(
            f"/api/loads/{load.id}/complete",
            {"driver_id": self.driver.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        load.refresh_from_db()
        self.assertEqual(load.status, "Completed")

        self.truck.refresh_from_db()
        self.assertEqual(str(self.truck.available_capacity), "750.00")

    def test_driver_profile_update_can_change_truck_details(self):
        response = self.client.put(
            "/api/user/update",
            {
                "userId": self.driver.id,
                "name": "Updated Driver",
                "phone": "03001234567",
                "truckType": "10-wheeler",
                "truckReg": "XYZ-999",
                "capacity": "1500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.driver.refresh_from_db()
        self.truck.refresh_from_db()

        self.assertEqual(self.driver.first_name, "Updated Driver")
        self.assertEqual(self.driver.phone_number, "03001234567")
        self.assertEqual(self.truck.truck_type, "10-wheeler")
        self.assertEqual(self.truck.registration_no, "XYZ-999")
        self.assertEqual(str(self.truck.total_capacity), "1500.00")

    def test_user_profile_can_be_loaded_by_email(self):
        response = self.client.get(f"/api/user/profile?email={self.driver.email}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], self.driver.email)
        self.assertEqual(data["truckType"], "Mazda")

    def test_user_loads_returns_all_loads_for_trader(self):
        pending_load = self.create_load("100.00", status="Pending")
        picked_load = self.create_load("200.00", status="Picked")
        picked_load.driver = self.driver
        picked_load.truck = self.truck
        picked_load.driver_current_latitude = "24.8607000"
        picked_load.driver_current_longitude = "67.0011000"
        picked_load.save()

        response = self.client.get(f"/api/user/loads?userId={self.trader.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_driver_location_sync_updates_all_picked_loads(self):
        first_load = self.create_load("200.00", status="Picked")
        first_load.driver = self.driver
        first_load.truck = self.truck
        first_load.save()

        second_load = self.create_load("300.00", status="Picked")
        second_load.driver = self.driver
        second_load.truck = self.truck
        second_load.save()

        response = self.client.post(
            "/api/driver/location-sync",
            {
                "driver_id": self.driver.id,
                "latitude": "24.8607000",
                "longitude": "67.0011000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first_load.refresh_from_db()
        second_load.refresh_from_db()
        self.assertEqual(str(first_load.driver_current_latitude), "24.8607000")
        self.assertEqual(str(second_load.driver_current_longitude), "67.0011000")
