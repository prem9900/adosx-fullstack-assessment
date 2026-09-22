from dataclasses import asdict

from rest_framework.decorators import api_view
from rest_framework.response import Response

from reconcile.models import Location, SourceEntry, SourceRecord
from reconcile.services.compare import REASONS, find_disagreements_for_org


@api_view(["GET"])
def orgs(request):
    """The tenant picker - every org_id that actually owns a location."""
    org_ids = sorted(set(Location.objects.values_list("org_id", flat=True)))
    return Response({"orgs": org_ids})


@api_view(["GET"])
def disagreements(request):
    """Disagreements for one tenant. org is required - there is no all-tenants view."""
    org_id = request.query_params.get("org")
    if not org_id:
        return Response({"detail": "org query param is required"}, status=400)

    records = list(SourceRecord.objects.all())
    entries = list(SourceEntry.objects.all())
    locations = list(Location.objects.all())

    results = find_disagreements_for_org(records, entries, locations, org_id)
    return Response({"reasons": REASONS, "results": [asdict(d) for d in results]})
