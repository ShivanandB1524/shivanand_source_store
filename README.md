# Shivanand. B Source Code Store — Account Layer

This project preserves the existing storefront and adds:
- Responsive Login / Signup popup
- Name + phone number + password account creation
- Password hashing on the Python server
- JWT login session
- My Account / Purchased Source Code library
- Server-side authorization before a source-code download
- Existing Razorpay payment links remain unchanged

## Project structure

- `templates/index.html` — your existing storefront plus account UI
- `static/account.css` — account popup styles
- `static/account.js` — login/signup/purchases frontend logic
- `app.py` — Flask + SQLite backend
- `protected_files/` — put purchased ZIP files here
- `requirements.txt` — Python dependencies

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set SOURCE_STORE_SECRET=replace-with-a-long-random-secret
set STORE_ADMIN_SECRET=replace-with-a-different-admin-secret
python app.py
```

Open `http://127.0.0.1:5000`.

## Important payment step

Your current buttons still point directly to Razorpay payment links. The browser must NOT be trusted to mark a purchase as paid.

After Razorpay confirms a payment, your server/webhook should call the protected purchase-grant flow (or, preferably, a dedicated Razorpay webhook handler) to create the row in `purchases`.

For testing only, the included `/api/admin/grant-purchase` endpoint can grant a purchase after setting `STORE_ADMIN_SECRET`.

## Production recommendations

1. Set a strong random `SOURCE_STORE_SECRET`.
2. Never expose `STORE_ADMIN_SECRET` in frontend JavaScript.
3. Replace the development grant endpoint with a verified Razorpay webhook.
4. Store the real ZIP files in `protected_files/` or object storage.
5. Serve the app over HTTPS.
6. Add rate limiting / OTP verification if you want phone-number-based account recovery.
