import time
import threading
import json
import requests
import re
from google import genai
from google.genai import types
from src.services import settings_manager as settings

class AIManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.lock = threading.Lock()
        self.settings_data = settings.load_settings()
        self.models = self.settings_data.get("ai_models", [])
        
        if not self.models:
            old_gemini_key = self.settings_data.get("gemini_api_key", "")
            old_gemini_model = self.settings_data.get("gemini_model", "gemini-2.5-flash")
            
            self.models = [
                {
                    "name": "Gemini Default",
                    "provider": "google",
                    "model": old_gemini_model if old_gemini_key else "gemini-2.5-flash",
                    "api_key": old_gemini_key,
                    "endpoint": "",
                    "quota": "-",
                    "link": "https://aistudio.google.com/app/apikey",
                    "status": "Sẵn sàng" if old_gemini_key else "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Groq Llama-3",
                    "provider": "openai",
                    "model": "llama-3.1-8b-instant",
                    "api_key": "",
                    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
                    "quota": "-",
                    "link": "https://console.groq.com/keys",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "GitHub Models",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "",
                    "endpoint": "https://models.inference.ai.azure.com/chat/completions",
                    "quota": "-",
                    "link": "https://github.com/marketplace/models",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "OpenRouter Free",
                    "provider": "openai",
                    "model": "google/gemma-2-9b-it:free",
                    "api_key": "",
                    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                    "quota": "-",
                    "link": "https://openrouter.ai/keys",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Together AI",
                    "provider": "openai",
                    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    "api_key": "",
                    "endpoint": "https://api.together.xyz/v1/chat/completions",
                    "quota": "-",
                    "link": "https://api.together.ai/settings/api-keys",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "DeepSeek Free",
                    "provider": "openai",
                    "model": "deepseek-chat",
                    "api_key": "",
                    "endpoint": "https://api.deepseek.com/chat/completions",
                    "quota": "-",
                    "link": "https://platform.deepseek.com/api_keys",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Mistral AI",
                    "provider": "openai",
                    "model": "mistral-tiny",
                    "api_key": "",
                    "endpoint": "https://api.mistral.ai/v1/chat/completions",
                    "quota": "-",
                    "link": "https://console.mistral.ai/api-keys/",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Hugging Face Serverless",
                    "provider": "openai",
                    "model": "Qwen/Qwen2.5-72B-Instruct",
                    "api_key": "",
                    "endpoint": "https://api-inference.huggingface.co/v1/chat/completions",
                    "quota": "-",
                    "link": "https://huggingface.co/settings/tokens",
                    "status": "Thiếu API Key",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                }
            ]
            self._save_models()
        
        # Dọn dẹp dữ liệu cũ (Xóa hardcoded quotas)
        for m in self.models:
            if m.get("api_key", "").strip() == "":
                m["status"] = "Thiếu API Key"
                m["quota"] = "-"
            elif not m.get("verified", False):
                m["status"] = "Chưa xác thực"
                m["quota"] = "Chưa xác định"
        self._save_models()
        
        self.notifications = []
        self.on_notification_callback = None
        
        # Bắt đầu luồng Polling ngầm
        self.polling_thread = threading.Thread(target=self._poll_exhausted_models, daemon=True)
        self.polling_thread.start()

    def verify_api_key(self, model_name, api_key):
        """Xác thực API Key thực tế và trích xuất hạn mức từ Header."""
        target = next((m for m in self.models if m["name"] == model_name), None)
        if not target:
            return False, "Lỗi", "Không tìm thấy model"

        if not api_key.strip():
            target["status"] = "Thiếu API Key"
            target["quota"] = "-"
            target["api_key"] = ""
            self._save_models()
            return False, "Thiếu API Key", "-"
            
        provider = target["provider"]
        endpoint = target.get("endpoint", "")
        model_id = target["model"]
        
        quota = "Chưa xác định"
        status = "Lỗi / Sai Key"
        is_valid = False
        
        try:
            if "openrouter.ai" in endpoint:
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=10)
                if resp.status_code == 200:
                    is_valid = True
                    data = resp.json()
                    limit = data.get("data", {}).get("rate_limit")
                    credits = data.get("data", {}).get("credit_limit")
                    quota_parts = []
                    if limit:
                        quota_parts.append(f"{limit['requests']} RPM")
                    if credits is not None:
                        quota_parts.append(f"${credits}")
                    if quota_parts:
                        quota = " | ".join(quota_parts)
            elif provider == "google":
                # Dùng google-genai SDK mới
                client = genai.Client(api_key=api_key)
                client.models.generate_content(model=model_id, contents="hi")
                is_valid = True
            else:
                if not endpoint:
                    endpoint = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    is_valid = True
                    rem_req = resp.headers.get("x-ratelimit-remaining-requests") or resp.headers.get("x-ratelimit-limit-requests")
                    rem_tok = resp.headers.get("x-ratelimit-remaining-tokens") or resp.headers.get("x-ratelimit-limit-tokens")
                    
                    if not rem_req and not rem_tok:
                        rem_req = resp.headers.get("x-ratelimit-limit-requests", "")
                    
                    quota_parts = []
                    if rem_req: quota_parts.append(f"{rem_req} req")
                    if rem_tok: quota_parts.append(f"{rem_tok} tok")
                    if quota_parts:
                        quota = " | ".join(quota_parts)
                elif resp.status_code == 429:
                    is_valid = True
                    quota = "Đang quá tải (429)"
                elif resp.status_code == 402:
                    is_valid = False
                    status = "Hết tiền (402)"
                    quota = "Hết Credit"
                    
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                is_valid = True
                quota = "Đang quá tải (429)"
            elif "402" in err or "balance" in err.lower() or "credit limit" in err.lower():
                is_valid = False
                status = "Hết tiền (402)"
                quota = "Hết Credit"
                
        if is_valid:
            status = "Sẵn sàng"
            target["verified"] = True
            
        target["api_key"] = api_key
        target["status"] = status
        target["quota"] = quota
        self._save_models()
        
        return is_valid, status, quota

    def _save_models(self):
        current_settings = settings.load_settings()
        current_settings["ai_models"] = self.models
        settings.save_settings(current_settings)

    def set_notification_callback(self, cb):
        self.on_notification_callback = cb

    def add_notification(self, msg):
        with self.lock:
            self.notifications.append({"time": time.time(), "msg": msg})
        if self.on_notification_callback:
            self.on_notification_callback()

    def get_notifications(self):
        with self.lock:
            return self.notifications.copy()

    def clear_notifications(self):
        with self.lock:
            self.notifications = []
        if self.on_notification_callback:
            self.on_notification_callback()

    def get_models(self):
        with self.lock:
            return self.models.copy()

    def update_models(self, new_models):
        with self.lock:
            self.models = new_models
            self._save_models()

    def _poll_exhausted_models(self):
        while True:
            time.sleep(10)
            
            models_to_ping = []
            with self.lock:
                now = time.time()
                for model in self.models:
                    if model.get("status") == "Exhausted":
                        wait_time = model.get("refresh_wait", 60)
                        exhausted_time = model.get("exhausted_time", 0)
                        if now - exhausted_time >= wait_time:
                            model["status"] = "Testing..."
                            models_to_ping.append(model)
            
            for model in models_to_ping:
                threading.Thread(target=self._ping_model, args=(model,), daemon=True).start()

    def _ping_model(self, model):
        success = False
        try:
            if model["provider"] == "google":
                client = genai.Client(api_key=model["api_key"])
                client.models.generate_content(model=model["model"], contents="hi")
                success = True
            elif model["provider"] == "openai":
                endpoint = model.get("endpoint", "https://api.openai.com/v1/chat/completions")
                headers = {"Authorization": f"Bearer {model['api_key']}", "Content-Type": "application/json"}
                payload = {"model": model["model"], "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    success = True
        except Exception:
            pass
            
        with self.lock:
            target = next((m for m in self.models if m["name"] == model["name"] and m["api_key"] == model["api_key"]), None)
            if target:
                if success:
                    target["status"] = "Sẵn sàng"
                    target["exhausted_time"] = 0
                    self.add_notification(f"Key '{target['name']}' đã hoạt động trở lại!")
                else:
                    target["status"] = "Exhausted"
                    target["refresh_wait"] = min(target.get("refresh_wait", 60) * 2, 3600)
                    target["exhausted_time"] = time.time()
                self._save_models()
                
        if self.on_notification_callback:
            self.on_notification_callback()

    def generate_diarization(self, system_instruction, user_prompt, log_callback=None, cancel_event=None):
        """Lặp qua danh sách model ưu tiên. Nếu lỗi 429 thì khóa model lại và chuyển tiếp."""
        models_to_try = self.get_models()
        if not models_to_try:
            raise Exception("Chưa có API Key nào được cấu hình. Vui lòng mở Dev Mode để thêm Model.")

        for model in models_to_try:
            import os
            api_key = model.get("api_key", "").strip()
            if not api_key:
                if model["provider"] == "google":
                    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
                elif model["provider"] == "openai":
                    if "groq" in model.get("endpoint", "").lower():
                        api_key = os.environ.get("GROQ_API_KEY", "").strip()
                    if not api_key:
                        api_key = os.environ.get("OPENAI_API_KEY", "").strip()

            with self.lock:
                target = next((m for m in self.models if m["name"] == model["name"]), None)
                if not target or target.get("status") == "Exhausted" or not api_key:
                    continue
            
            if log_callback:
                log_callback(f"🧠 Đang gọi API qua Model: {model['name']}")
                
            try:
                if model["provider"] == "google":
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model=model["model"],
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                        ),
                    )
                    clean_text = response.text.strip()
                elif model["provider"] == "openai":
                    endpoint = model.get("endpoint", "https://api.openai.com/v1/chat/completions")
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": model["model"], 
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                    resp = requests.post(endpoint, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}: {resp.text}")
                    data = resp.json()
                    clean_text = data['choices'][0]['message']['content'].strip()
                else:
                    continue

                    
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                elif clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                
                return clean_text.strip()
                
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "quota" in err_msg or "rate limit" in err_msg
                
                if is_rate_limit:
                    if log_callback:
                        log_callback(f"⚠️ Model '{model['name']}' hết Quota. Tự động nhảy sang model tiếp theo...")
                    
                    wait_time = 60
                    if "retry in" in err_msg:
                        match = re.search(r"retry in (\d+\.?\d*)s", err_msg)
                        if match:
                            wait_time = float(match.group(1)) + 5.0
                            
                    with self.lock:
                        target = next((m for m in self.models if m["name"] == model["name"]), None)
                        if target:
                            target["status"] = "Exhausted"
                            target["exhausted_time"] = time.time()
                            target["refresh_wait"] = wait_time
                        self._save_models()
                        
                    self.add_notification(f"Model '{model['name']}' báo lỗi 429. Bắt đầu test ngầm chờ hồi phục.")
                else:
                    if log_callback:
                        log_callback(f"⚠️ Lỗi Model '{model['name']}': {err_msg}")

        raise Exception("Tất cả các Model đều quá tải hoặc báo lỗi. Hãy chờ một lúc hoặc thêm Model mới.")
