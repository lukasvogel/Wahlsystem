from django.shortcuts import render
from django.template import RequestContext

from .models import BundestagMembers
from .models import ClosestWinners
from .models import Overhang
from .models import Overview
from .models import Wahlkreise

ov = Overview()



def index(request):
    context = RequestContext(request)

    return render(request, 'overview.html', context)


def overview(request, e_id):
    context = RequestContext(request, {
        'parties': ov.get_composition(e_id),
        'bar_series': ov.get_percentages(list(range(1, int(e_id) + 1))),
        'election': e_id
    })

    return render(request, 'overview.html', context)


def wk_overview(request, e_id):
    context = RequestContext(request, {
        'wahlkreise': Wahlkreise.get_overview(e_id),
        'election': e_id
    })

    return render(request, 'wk_overview.html', context)


def wk_detail(request, e_id, wk_id):
    context = RequestContext(request, {
        'details': Wahlkreise.get_details(wk_id, e_id),
        'election': e_id
    })

    return render(request, 'wk_detail.html', context)


def bundestag_overview(request, e_id):
    context = RequestContext(request, {
        'members': BundestagMembers.get_members(e_id),
        'election': e_id
    })

    return render(request, 'abgeordnete.html', context)


def ks_overview(request, e_id):
    context = RequestContext(request, {
        'parties': ClosestWinners.overview(e_id),
        'election': e_id
    })
    return render(request, 'closest_outcome_overview.html', context)


def ks_detail(request, e_id, party_id):
    context = RequestContext(request, {
        'closest': ClosestWinners.get_winners(e_id, party_id),
        'party_id': party_id,
        'election': e_id

    })

    return render(request, 'closest_outcome_detail.html', context)


def overhang_overview(request, e_id):
    context = RequestContext(request, {
        'mandates': Overhang.get_overhang(e_id),
        'election': e_id
    })

    return render(request, 'overhang_overview.html', context)
