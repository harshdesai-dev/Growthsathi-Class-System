from tests.test_academic_scopes import AcademicFixture


class ModuleFilterTests(AcademicFixture):
    def test_student_filters_combine_search_and_current_batch(self):
        response = self.get(f"students/?batch={self.batch.pk}&search=student&status=ACTIVE")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["results"]], [self.sp.pk])
        self.assertEqual(
            self.get(f"students/?batch={self.next_batch.pk}&search=student").json()["count"], 0
        )
        self.assertEqual(self.get("students/?batch=invalid").status_code, 400)

    def test_assignment_filters_do_not_resurrect_removed_relationships(self):
        self.assertEqual(self.get(f"teachers/?batch={self.batch.pk}").json()["count"], 1)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.get(f"teachers/?batch={self.batch.pk}").json()["count"], 0)

    def test_parent_filter_requires_active_link(self):
        self.assertEqual(self.get(f"parents/?batch={self.batch.pk}").json()["count"], 1)
        self.link.is_active = False
        self.link.save()
        self.assertEqual(self.get(f"parents/?batch={self.batch.pk}").json()["count"], 0)

    def test_student_and_teacher_cannot_expand_scope_with_filters(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"students/?batch={self.next_batch.pk}").json()["count"], 0)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(f"batches/?class={self.academic_class.pk}").json()["count"], 1)
        self.assertEqual(self.get(f"fees/?batch={self.batch.pk}&search=student").status_code, 403)
        self.assertEqual(self.get("attendance/?date_from=not-a-date").status_code, 400)
