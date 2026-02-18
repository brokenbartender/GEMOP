import os
import tempfile

def check_unicode_decoding():
    test_string = "Hello, world! 👋 Привет мир! こんにちは世界！"
    test_filename = None
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False) as temp_file:
            test_filename = temp_file.name
            temp_file.write(test_string)
            temp_file.flush() # Ensure all data is written to disk

        print(f"Wrote unicode string to: {test_filename}")

        # Read the file back with UTF-8 encoding
        with open(test_filename, 'r', encoding='utf-8') as f:
            read_string = f.read()

        print(f"Read string: '{read_string}'")

        # Verify the content
        if read_string == test_string:
            print("Unicode string successfully written and read back with UTF-8 encoding.")
            return True
        else:
            print("Mismatch between original and read string.")
            return False

    except UnicodeDecodeError as e:
        print(f"UnicodeDecodeError encountered: {e}")
        return False
    except Exception as e:
