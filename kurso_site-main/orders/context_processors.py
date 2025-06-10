from disputes.models import Dispute
from payments.models import PriceProposal


def dispute_notifications(request):
    if request.user.is_staff:
        pending_count = Dispute.objects.filter(status='pending').count()
        return {'pending_disputes_count': pending_count}
    return {}

