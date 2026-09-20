import os
from unittest import skipUnless

from django.db import connection
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView


class FoundationTests(SimpleTestCase):
    def test_health_is_minimal_and_not_cached(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_health_rejects_mutations(self):
        self.assertEqual(self.client.post("/health/").status_code, 405)

    def test_unconfigured_api_denies_anonymous_access(self):
        response = APIView.as_view()(APIRequestFactory().get("/"))
        self.assertEqual(response.status_code, 401)


@skipUnless(os.getenv("RUN_DATABASE_TESTS", "").lower() == "true", "Opt-in PostgreSQL test")
class PostgreSQLTests(TestCase):
    databases = {"default"} if os.getenv("RUN_DATABASE_TESTS", "").lower() == "true" else set()

    def test_postgresql_connection(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone(), (1,))
