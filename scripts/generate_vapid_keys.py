"""
تولید کلید VAPID (خصوصی/عمومی) برای Web Push — این کلیدها یک‌بار در .env
ذخیره می‌شوند و ثابت می‌مانند (تغییرشان یعنی همه اشتراک‌های قبلی کاربران باطل می‌شود).

اجرا:
    python -m scripts.generate_vapid_keys
خروجی دو خط است: خط اول کلید عمومی، خط دوم کلید خصوصی.
"""
import base64

from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_vapid_keys() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_numbers = private_key.private_numbers()
    private_raw = private_numbers.private_value.to_bytes(32, "big")

    public_numbers = public_key.public_numbers()
    public_raw = b"\x04" + public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")

    return _b64url(public_raw), _b64url(private_raw)


if __name__ == "__main__":
    public_key, private_key = generate_vapid_keys()
    print(public_key)
    print(private_key)
