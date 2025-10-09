import jwt
from os import environ
from datetime import datetime, timedelta, timezone
from fastapi.responses import JSONResponse


def create_jwt(
    payload: dict, secret: str, algorithm: str = "HS256", lifetime_minutes: int = 2
) -> str:
    """Creates a JSON Web Token (JWT) with the given payload, secret, and expiration time.

    Args:
        payload (dict): The payload to include in the JWT.
        secret (str): The secret key used to sign the JWT.
        algorithm (str, optional): The algorithm to use for signing. Defaults to "HS256".
        lifetime_minutes (int, optional): Token lifetime in minutes
        . Defaults to 45.

    Returns:
        str: The encoded JWT as a string.
    """
    exp = datetime.now(tz=timezone.utc) + timedelta(minutes=lifetime_minutes)
    exp = int(exp.timestamp())
    return jwt.encode({**payload, "exp": exp}, secret, algorithm=algorithm)


def decode_jwt(token: str, secret: str, algorithms: list = ["HS256"]) -> dict:
    """Decodes and verifies a JSON Web Token (JWT) using the provided secret and algorithms.

    Args:
        token (str): The JWT to decode.
        secret (str): The secret key used to verify the JWT.
        algorithms (list, optional): List of acceptable algorithms. Defaults to ["HS256"].

    Returns:
        dict: The decoded payload of the JWT.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid for any other reason.
    """
    return jwt.decode(token, secret, algorithms=algorithms)


def is_jwt_valid(
    token: str, secret: str, algorithms: list = ["HS256"]
) -> tuple[bool, bool]:
    """Checks if a JSON Web Token (JWT) is valid and not expired.

    Args:
        token (str): The JWT to validate.
        secret (str): The secret key used to verify the JWT.
        algorithms (list, optional): List of acceptable algorithms. Defaults to ["HS256"].

    Returns:
        tuple[bool, bool]: A tuple where the first element indicates if the token is valid,
        and the second element indicates if the token is expired.
    """
    try:
        decode_jwt(token, secret, algorithms)
        return True, False
    except jwt.ExpiredSignatureError:
        return True, True
    except jwt.InvalidTokenError:
        return False, False


def get_jwt_from_request(request) -> str | None:
    cookie = request.headers.get("cookie", "")
    cookies = {
        item.split("=")[0]: item.split("=")[1]
        for item in cookie.split("; ")
        if "=" in item
    }
    return cookies.get("JWT", None)


async def handle_root_path(request, call_next):
    if request.url.path == "/":
        current_token = get_jwt_from_request(request)
        token = None
        if not current_token:
            token = create_jwt(
                {"role": "installer"},
                environ.get("JWT_SECRET", "default_secret"),
            )
        response = await call_next(request)
        if token is not None:
            response.set_cookie(
                "JWT", token, httponly=True, samesite="strict", secure=True
            )
        return response
    response = await call_next(request)
    return response


async def jwt_middleware(request, call_next):
    IGNORED_PATHS = ["/static", "/trigger-reload"]
    # Example: Check for JWT in Authorization header
    jwt_cookie = get_jwt_from_request(request)
    current_path = request.url.path

    # Bypass JWT check on root and any ignored paths
    if current_path == "/":
        response = await handle_root_path(request, call_next)
        return response

    # Bypass any ignored paths
    if any(current_path.startswith(p) for p in IGNORED_PATHS):
        response = await call_next(request)
        return response

    # All other routes require a valid JWT
    if jwt_cookie is not None:
        try:

            isValid, isExpired = is_jwt_valid(
                jwt_cookie, secret=environ.get("JWT_SECRET", "default_secret")
            )
            # if we had a valid but expired token, create a new one
            if isExpired and isValid:
                token = create_jwt(
                    {"role": "installer"},
                    environ.get("JWT_SECRET", "default_secret"),
                )
                # handle the request and set the new cookie
                response = await call_next(request)
                response.set_cookie(
                    "JWT", token, httponly=True, samesite="strict", secure=True
                )
                return response

            # if the token is not valid or is expired, (should not be expired) reject the request
            if not isValid or isExpired:
                print("Invalid or expired JWT token.")
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid token"}
                )

        except Exception as _:
            print("No JWT provided in request:", _)

            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
    else:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    # If JWT is valid, proceed with the request
    response = await call_next(request)
    return response
