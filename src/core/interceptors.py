import re

class CancelException(BaseException):
    pass

class TqdmInterceptor:
    """Intercepts sys.stderr to parse Whisper's tqdm output and send it to GUI."""
    def __init__(self, callback, original_stderr, log_callback=None, cancel_event=None, lang_callback=None):
        self.callback = callback
        self.original_stderr = original_stderr
        self.log_callback = log_callback
        self.cancel_event = cancel_event
        self.lang_callback = lang_callback
        # Regex matches tqdm string, e.g. "58%|███   | 53900/92512 [09:20<07:01, 91.65frames/s]"
        self.pattern = re.compile(r'(\d+)%\|.*\|\s*(\d+/\d+)\s*\[(.*?)\]')

    def write(self, s):
        if self.cancel_event and self.cancel_event.is_set():
            raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

        # Always output to original stderr to ensure terminal behaves normally
        self.original_stderr.write(s)
        
        if "%|" in s:
            match = self.pattern.search(s)
            if match and self.callback:
                percent_str = match.group(1)
                progress_stats = match.group(2) + " [" + match.group(3) + "]"
                try:
                    percent = float(percent_str)
                    self.callback(percent, progress_stats)
                except ValueError:
                    pass
        elif "Detected language:" in s:
            lang_name = s.split("Detected language:")[-1].strip()
            if self.log_callback:
                self.log_callback("[Whisper] ✅ " + s.strip())
            if self.lang_callback:
                self.lang_callback(lang_name)

    def flush(self):
        self.original_stderr.flush()

class StdoutInterceptor:
    """Intercepts sys.stdout to catch 'Detected language' which whisper prints to stdout."""
    def __init__(self, original_stdout, lang_callback=None, log_callback=None):
        self.original_stdout = original_stdout
        self.lang_callback = lang_callback
        self.log_callback = log_callback

    def write(self, s):
        self.original_stdout.write(s)
        if "Detected language:" in s:
            lang_name = s.split("Detected language:")[-1].strip()
            if self.log_callback:
                self.log_callback("[Whisper] ✅ " + s.strip())
            if self.lang_callback:
                self.lang_callback(lang_name)

    def flush(self):
        self.original_stdout.flush()
