headers = {
    "Content-Type": "application/json",
    "Authorization": get_cognito_auth_token(),
}
apps_with_problems = []
utc = pytz.utc
start = datetime.datetime.utcnow() - datetime.timedelta(days=30)
start_utc = utc.localize(start)


statuses = [
    Application.STATUS_PRE_APPROVED, Application.STATUS_PASSED, Application.STATUS_CURRENT, Application.STATUS_LATE,
    Application.STATUS_CHARGEOFF, Application.STATUS_RETURN, Application.STATUS_RETURN_PENDING,
    Application.STATUS_BUYOUT, Application.STATUS_SETTLEMENT, Application.STATUS_BANKRUPTCY,
    Application.STATUS_COMPLETE, Application.STATUS_SOLD, Application.STATUS_CANCELLED, Application.STATUS_PENDING,
    Application.STATUS_TIMED_OUT, Application.STATUS_VERIFICATION_REQUIRED
]
open_status = [
    Application.STATUS_LATE,
    Application.STATUS_CURRENT,
    Application.STATUS_CHARGEOFF,
    Application.STATUS_RETURN_PENDING
]

apps = Application.objects.filter(status__in=statuses, user_id__in=cogs)
# apps = Application.objects.filter(status__in=statuses, updated_at__gte=start_utc)

ids = []
count = 0
for app in apps:
    try:
        if app.user_id in ids or app.user_id is None:
            continue
        count = count + 1
        ids.append(app.user_id)
        all_related_apps = app.user.application_set.all()
        up = app.user.get_profile()
        preapp = PreApproval.objects.filter(application__user=app.user).first()
        notifs = UserLmsNotification.objects.filter(user=app.user)
        db_sms_obj = notifs.first()
        locale = Locale.get_by_state(app.billing_state)

        #get most recent preapproval
        recent_preapp = Application.objects.filter(status=Application.STATUS_PRE_APPROVED, user_id__in=[app.user_id]).order_by('-created_at').first()

        # Posting to Hubspot
        data = {
            "event_type": "CONTACT",
            "user_id": app.user_id,
            "billing_first_name": up.billing_first_name.capitalize() if up.billing_first_name else None,
            "billing_last_name": up.billing_last_name.capitalize() if up.billing_last_name else None,
            "billing_state": str(locale),
            "billing_address": (up.billing_address or '') + ' ' + (up.billing_address2 or ''),
            "billing_city": up.billing_city,
            "billing_zip": up.billing_zip,
            "phone": up.phone,
            "email": app.user.email,
            "approval_limit": str(up.approval_limit),
            "available_limit": str(up.available_limit),
            "user_lease_cnt": all_related_apps.filter(payment_settled=True).count(),
            "opt_out": db_sms_obj.opt_out,
            "expiration_date": preapp.expiration_date.strftime('%m/%d/%Y'),
            "application_created_at": app.created_at.strftime('%m/%d/%Y'),
            "retailer_dba": recent_preapp.retailer.dba if recent_preapp.retailer.dba else recent_preapp.retailer.name,
            "user_open_lease_cnt": all_related_apps.filter(status__in=open_status).count(),
            "4digit_ssn" : app.get_ssn4(),
            "dob" : app.dob.strftime('%m/%d/%Y') if app.dob else None
        }
        recent_user = Application.objects.filter(status__in=statuses, user_id=app.user_id).order_by('created_at').first()
        today = datetime.datetime.utcnow().date()
        if today > recent_user.created_at.date():
            data["operation"] = 'UPDATE'
        else:
            data["operation"] = "CREATE"
        data["operation"] = 'UPDATE'

        print(data)
        resp = requests.post(url=settings.HUBSPOT_API, data=json.dumps(data), headers=headers)
        if resp.status_code != 200:
            print('Hubspot Deal: Return Status as Failure')

        if count%1000==0:
            # time.sleep(5)
            headers = {
                "Content-Type": "application/json",
                "Authorization": get_cognito_auth_token(),
            }
            print(count)

    except Exception as e:
        print("Buggy app (id: {0}, error:{1})".format(app.id, e))
        apps_with_problems.append({
            "app": app.id,
            "status": app.status,
            "error": str(e)
        })
