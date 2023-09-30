from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Payment, Expense, Regarding, User
from core.serializers import RegardingSerializerReader
import json


class Command(BaseCommand):
    help = "Update the balance_json and close the regardings that had finished"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.today = timezone.now().date()

    def handle(self, *args, **options):
        regardings = self.get_regardings()
        self.update_regadings_balance_json(regardings)
        open_regardings = regardings.filter(is_closed=False, end_date__lt=self.today)
        self.close_regadings(open_regardings)

    def get_regardings(self):
        regardings = Regarding.objects.select_related("expense_group")
        return regardings

    def close_regadings(self, regardings):
        regardings.update(is_closed=True)

    def update_regadings_balance_json(self, regardings):
        for regarding in regardings:
            regarding.balance_json = {}
            regarding.is_closed = False
            regarding_serializer = RegardingSerializerReader(regarding, context={"request": {"user": User.objects.first()}})
            totals = regarding_serializer.data
            regarding.balance_json = json.dumps({
                "general_total": totals.get('general_total', {}),
                "consumer_total": totals.get('consumer_total', []),
                "total_by_day": totals.get('total_by_day', {}),
                "total_member_vs_member": totals.get('total_member_vs_member', {}),
            }, default=str)
        print(f"{regardings.count()} regardings updated")
        Regarding.objects.bulk_update(regardings, ['balance_json'], batch_size=2000)
