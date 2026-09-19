"""Allowlisted filters applied only after each view establishes authorization scope."""

from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend


class ModuleFilters(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        mapping = getattr(view, "module_filters", {})
        values = {}
        kinds = {
            "id": serializers.IntegerField(min_value=1),
            "date": serializers.DateField(),
            "bool": serializers.BooleanField(),
            "text": serializers.CharField(max_length=120),
        }
        for parameter, (lookup, kind) in mapping.items():
            raw = request.query_params.get(parameter)
            if raw not in (None, ""):
                values[lookup] = kinds[kind].run_validation(raw)
                values.update(getattr(view, "filter_constraints", {}).get(parameter, {}))
        return queryset.filter(**values).distinct() if values else queryset
