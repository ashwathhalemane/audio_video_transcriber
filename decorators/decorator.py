from functools import wraps
import time


def retry_on_exception(max_attempts=3, wait_time=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    attempts += 1
                    print(f"Attempt {attempts} failed: {error}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator


# Counter to track number of function calls
attempt_counter = 0

# Example function using the decorator for retry logic
@retry_on_exception(max_attempts=3, wait_time=2)
def fetch_data():
    global attempt_counter
    attempt_counter += 1
    if attempt_counter < 3:
        raise ValueError(f"Request failed on attempt {attempt_counter}!")
    return "Data fetched successfully"

# Execute the function once, it will retry automatically
response = fetch_data()
print(response)