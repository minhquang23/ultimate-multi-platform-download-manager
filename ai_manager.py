import time
import threading
import json
import requests
import re
import google.generativeai as genai
import settings

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
                    "quota": "15 RPM | 1M TPM",
                    "link": "https://aistudio.google.com/app/apikey",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Groq Llama-3",
                    "provider": "openai",
                    "model": "llama-3.1-8b-instant",
                    "api_key": "",
                    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
                    "quota": "30 RPM | 6K TPM",
                    "link": "https://console.groq.com/keys",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "GitHub Models",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "",
                    "endpoint": "https://models.inference.ai.azure.com/chat/completions",
                    "quota": "15 RPM | 150 RPD",
                    "link": "https://github.com/marketplace/models",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "OpenRouter Free",
                    "provider": "openai",
                    "model": "google/gemma-2-9b-it:free",
                    "api_key": "",
                    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                    "quota": "20 RPM",
                    "link": "https://openrouter.ai/keys",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                },
                {
                    "name": "Together AI",
                    "provider": "openai",
                    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    "api_key": "",
                    "endpoint": "https://api.together.xyz/v1/chat/completions",
                    "quota": "60 RPM",
                    "link": "https://api.together.ai/settings/api-keys",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "DeepSeek Free",
                    "provider": "openai",
                    "model": "deepseek-chat",
                    "api_key": "",
                    "endpoint": "https://api.deepseek.com/chat/completions",
                    "quota": "Bonus Credit",
                    "link": "https://platform.deepseek.com/api_keys",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Mistral AI",
                    "provider": "openai",
                    "model": "mistral-tiny",
                    "api_key": "",
                    "endpoint": "https://api.mistral.ai/v1/chat/completions",
                    "quota": "Experiment Plan",
                    "link": "https://console.mistral.ai/api-keys/",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                },
                {
                    "name": "Hugging Face Serverless",
                    "provider": "openai",
                    "model": "Qwen/Qwen2.5-72B-Instruct",
                    "api_key": "",
                    "endpoint": "https://api-inference.huggingface.co/v1/chat/completions",
                    "quota": "Dynamic",
                    "link": "https://huggingface.co/settings/tokens",
                    "status": "Sẵn sàng",
                    "exhausted_time": 0,
                    "refresh_wait": 0
                }
            ]
            self._save_models()
        
        self.notifications = []
        self.on_notification_callback = None
        
        # Bắt đầu luồng Polling ngầm
        self.polling_thread = threading.Thread(target=self._poll_exhausted_models, daemon=True)
        self.polling_thread.start()

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
            time.sleep(10) # check every 10 seconds
            
            models_to_ping = []
            with self.lock:
                now = time.time()
                for model in self.models:
                    if model.get("status") == "Exhausted":
                        # Check if refresh time has passed
                        wait_time = model.get("refresh_wait", 60)
                        exhausted_time = model.get("exhausted_time", 0)
                        if now - exhausted_time >= wait_time:
                            model["status"] = "Testing..."
                            models_to_ping.append(model)
            
            # Ping outside lock to prevent blocking UI
            for model in models_to_ping:
                threading.Thread(target=self._ping_model, args=(model,), daemon=True).start()

    def _ping_model(self, model):
        """Đốt 1 lượng token tối thiểu để kiểm tra xem API đã hồi phục chưa."""
        success = False
        try:
            if model["provider"] == "google":
                genai.configure(api_key=model["api_key"])
                m = genai.GenerativeModel(model["model"])
                # Gửi chuỗi siêu ngắn
                m.generate_content("hi")
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
            # Tìm lại model trong danh sách thực tế để cập nhật (tránh race condition)
            target = next((m for m in self.models if m["name"] == model["name"] and m["api_key"] == model["api_key"]), None)
            if target:
                if success:
                    target["status"] = "Sẵn sàng"
                    target["exhausted_time"] = 0
                    self.add_notification(f"Key '{target['name']}' đã hoạt động trở lại!")
                else:
                    target["status"] = "Exhausted"
                    # Tăng thời gian chờ lên gấp đôi (Max 1 hour)
                    target["refresh_wait"] = min(target.get("refresh_wait", 60) * 2, 3600)
                    target["exhausted_time"] = time.time()
                self._save_models()
                
        if self.on_notification_callback:
            self.on_notification_callback()

    def generate_diarization(self, system_instruction, user_prompt, log_callback=None, cancel_event=None):
        """
        Lặp qua danh sách model ưu tiên. Nếu lỗi 429 thì khóa model lại và chuyển tiếp.
        """
        models_to_try = self.get_models()
        if not models_to_try:
            raise Exception("Chưa có API Key nào được cấu hình. Vui lòng mở Dev Mode để thêm Model.")

        for model in models_to_try:
            # Re-check status inside lock to ensure it hasn't changed
            with self.lock:
                target = next((m for m in self.models if m["name"] == model["name"]), None)
                if not target or target.get("status") == "Exhausted":
                    continue
            
            if log_callback:
                log_callback(f"🧠 Đang gọi API qua Model: {model['name']}")
                
            try:
                if model["provider"] == "google":
                    genai.configure(api_key=model["api_key"])
                    m = genai.GenerativeModel(model["model"])
                    response = m.generate_content(system_instruction + "\n\n" + user_prompt)
                    clean_text = response.text.strip()
                elif model["provider"] == "openai":
                    endpoint = model.get("endpoint", "https://api.openai.com/v1/chat/completions")
                    headers = {"Authorization": f"Bearer {model['api_key']}", "Content-Type": "application/json"}
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
                    
                # Xử lý text trả về
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
