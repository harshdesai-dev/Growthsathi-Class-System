import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from exams.models import ExamScore
from tests.test_academic_scopes import AcademicFixture


class ContentWorkflowTests(AcademicFixture):
    def exam(self):
        response = self.post(
            "exams/",
            {
                "name": "Unit test",
                "batch": self.batch.pk,
                "subject": self.subject.pk,
                "date": str(timezone.localdate()),
                "starts_at": "10:00",
                "total_marks": "50",
                "passing_marks": "20",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_exam_marks_publication_and_private_results_flow(self):
        exam = self.exam()
        score = ExamScore.objects.get(exam_id=exam)
        self.assertEqual(
            self.post(f"exams/{exam}/publication/", {"published": True}).status_code, 400
        )
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(f"exams/{exam}/marks/").status_code, 200)
        self.assertEqual(
            self.post(f"exams/{exam}/publication/", {"published": True}).status_code, 403
        )
        self.assertEqual(
            self.post(
                f"exams/{exam}/marks/", {"scores": [{"score": score.pk, "marks": "51"}]}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                f"exams/{exam}/marks/", {"scores": [{"score": score.pk, "marks": "42"}]}
            ).status_code,
            200,
        )
        for user in [self.student, self.parent]:
            self.client.force_authenticate(user)
            self.assertEqual(self.get("results/").json()["count"], 0)
            self.assertEqual(self.get(f"exams/{exam}/marks/").status_code, 403)
            self.assertNotIn("scores", self.get(f"exams/{exam}/").json())
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.post(f"exams/{exam}/publication/", {"published": True}).status_code, 200
        )
        for user in [self.student, self.parent]:
            self.client.force_authenticate(user)
            result = self.get(f"results/{score.pk}/")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(
                result.json()["calculation"], {"percentage": "84.00", "result": "PASS"}
            )
            self.assertEqual(self.get(f"results/{score.pk}/report_card/").status_code, 200)
        self.client.force_authenticate(self.peer)
        self.assertEqual(self.get(f"results/{score.pk}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.post(f"exams/{exam}/publication/", {"published": False})
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"results/{score.pk}/").status_code, 404)

    def test_removed_assignment_cannot_enter_marks(self):
        exam = self.exam()
        self.assignment.is_active = False
        self.assignment.save()
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(f"exams/{exam}/").status_code, 404)
        self.assertEqual(self.post(f"exams/{exam}/marks/", {"scores": []}).status_code, 404)

    def test_material_upload_download_and_private_student_document(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.client.force_authenticate(self.teacher)
            upload = self.client.post(
                "/api/files/",
                {"file": SimpleUploadedFile("notes.pdf", b"%PDF-1.4\nDemo")},
                HTTP_HOST="a.test",
            )
            self.assertEqual(upload.status_code, 201)
            asset = upload.json()["id"]
            response = self.post(
                "materials/",
                {
                    "title": "Algebra",
                    "batch": self.batch.pk,
                    "subject": self.subject.pk,
                    "file_asset": asset,
                },
            )
            self.assertEqual(response.status_code, 201)
            material = response.json()["id"]
            self.client.force_authenticate(self.student)
            self.assertEqual(self.get(f"materials/{material}/").status_code, 200)
            download = self.get(f"materials/{material}/download/")
            self.assertEqual(download.status_code, 200)
            self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4\nDemo")
            self.client.force_authenticate(self.peer)
            self.assertEqual(self.get(f"materials/{material}/").status_code, 404)
            self.assertEqual(self.get(f"files/{asset}/").status_code, 403)
            self.client.force_authenticate(self.admin)
            upload = self.client.post(
                "/api/files/",
                {
                    "file": SimpleUploadedFile("private.pdf", b"%PDF-1.4\nPrivate"),
                    "student": self.sp.pk,
                },
                HTTP_HOST="a.test",
            )
            private = upload.json()["id"]
            for user in [self.student, self.parent, self.teacher]:
                self.client.force_authenticate(user)
                self.assertEqual(self.get(f"files/{private}/").status_code, 403)
            self.client.force_authenticate(self.teacher)
            bad = self.client.post(
                "/api/files/",
                {"file": SimpleUploadedFile("bad.pdf", b"MZ executable")},
                HTTP_HOST="a.test",
            )
            self.assertEqual(bad.status_code, 400)
