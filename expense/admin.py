from django.contrib import admin
from expense.models import RideExpense, RideExpenseComment, RideExpenseDocs, PaymentMode

admin.site.register(RideExpense)
admin.site.register(RideExpenseComment)
admin.site.register(RideExpenseDocs)
admin.site.register(PaymentMode)
