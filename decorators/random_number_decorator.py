from functools import wraps
import time
import random

# TODO: enhance a Python function that checks whether a random number is greater than 8 
# with retries and failure handling using Python decorators. 
# Task is to complete the decorator and see how the function retries up to ten times before succeeding or stopping!
def retry_on_exception(max_attempts, wait_time):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
             # TODO: implement the retry logic
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    attempts += 1
                    print(f"Attempt {attempts} failed: {error}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        return wrapper
    return decorator


# Example function using the decorator for retry logic
@retry_on_exception(max_attempts=5, wait_time=1)
def check_random_number():
    num = random.randint(1, 10)
    if num <= 8:
        raise ValueError(f"Number {num} is not greater than 8.")
    return f"Number {num} is greater than 8."


# Execute the function once, it will retry automatically
response = check_random_number()
print(response)