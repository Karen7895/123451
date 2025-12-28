import customtkinter as ctk
import json
import os
import requests
import httpx
from bs4 import BeautifulSoup
import pyperclip
from datetime import datetime, timedelta
from threading import Thread
import random


class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LingvoMaster Pro")
        self.geometry("1000x650")
        self.minsize(900, 600)

        # Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Data + UI
        self.initialize_data()
        self.setup_main_ui()

    # =========================
    # Data / Storage
    # =========================
    def initialize_data(self):
        self.word_stats = {"total": 0, "day": 0, "week": 0, "month": 0}
        self.test_stats = {
            "best_score": 0,
            "average_score": 0,
            "streak": 0,
            "total_reviews": 0,
            "best_day": None,
            "accuracy_by_type": {}
        }

        self.daily_goal = 10
        self.daily_progress = 0

        os.makedirs("logs", exist_ok=True)
        self.words_file = "logs/user_words.json"
        self.history_file = "logs/training_history.json"

        self.words = self.load_words()
        self.training_history = self.load_history()
        self.word_stats["total"] = len(self.words)

        self.last_selected_topic = "Все темы"

        # AI Chat config (лучше держать ключ в переменной окружения)
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")  # <- положи ключ в переменную окружения
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://www.webstylepress.com",
            "X-Title": "WebStylePress",
            "Content-Type": "application/json"
        }

        self.languages = {
            "Auto Detect": "auto", "Armenian": "hy", "English": "en", "French": "fr",
            "Spanish": "es", "German": "de", "Russian": "ru", "Chinese": "zh",
            "Japanese": "ja", "Korean": "ko", "Italian": "it", "Portuguese": "pt",
            "Dutch": "nl", "Arabic": "ar", "Hindi": "hi", "Turkish": "tr",
            "Hebrew": "he", "Greek": "el", "Swedish": "sv", "Polish": "pl",
            "Ukrainian": "uk", "Czech": "cs", "Finnish": "fi", "Hungarian": "hu",
            "Romanian": "ro", "Thai": "th", "Vietnamese": "vi", "Indonesian": "id"
        }

    def ensure_word_defaults(self, word: dict) -> dict:
        word.setdefault("topic", "Без темы")
        word.setdefault("tags", [])
        word.setdefault("status", "New")
        word.setdefault("review_count", 0)
        word.setdefault("last_reviewed", None)
        return word

    def load_words(self):
        try:
            if os.path.exists(self.words_file):
                with open(self.words_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        return [self.ensure_word_defaults(w) for w in loaded if isinstance(w, dict)]
        except Exception as e:
            print(f"Error loading words: {e}")
        return []

    def save_words(self):
        try:
            with open(self.words_file, "w", encoding="utf-8") as f:
                json.dump(self.words, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving words: {e}")

    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error loading history: {e}")
        return []

    def save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.training_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def log_review(self, word: dict, correct: bool, test_type: str = "practice"):
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "wordId": word.get("word"),
            "result": "correct" if correct else "incorrect",
            "testType": test_type,
            "sessionId": datetime.now().strftime("%Y%m%d%H%M%S"),
            "timestamp": datetime.now().isoformat()
        }
        self.training_history.append(entry)
        self.save_history()

    # =========================
    # Topics / Filters helpers
    # =========================
    def get_topics(self):
        topics = {w.get("topic", "Без темы") for w in self.words}
        return sorted(topics)

    def get_words_for_quiz(self, selected_topic: str):
        if selected_topic == "Все темы":
            return list(self.words)
        return [w for w in self.words if w.get("topic", "Без темы") == selected_topic]

    def get_today_words(self):
        if not self.words:
            return []
        return self.words[:min(self.daily_goal, len(self.words))]

    # =========================
    # UI Shell
    # =========================
    def setup_main_ui(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_menu()

        self.content_frame = ctk.CTkFrame(self, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        self.show_main_screen()

    def setup_menu(self):
        menu_frame = ctk.CTkFrame(self, corner_radius=0)
        menu_frame.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            menu_frame, text="LingvoMaster", font=("Arial", 22, "bold"), pady=30
        ).pack()

        ctk.CTkFrame(menu_frame, height=2, fg_color=("#D0D0D0", "#404040")).pack(fill="x", padx=20)

        buttons = [
            ("➕ Add Word", self.show_add_word_screen),
            ("🔍 Search", self.show_search_screen),
            ("📖 All Words", self.show_all_words),
            ("🏷️ Topics", self.show_topics_screen),
            ("🗑️ Delete Word", self.show_delete_word_screen),
            ("✏️ Practice", self.show_topic_selection),
            ("🌐 Translator", self.show_translator),
            ("🤖 AI Chat", self.show_ai_chat),
            ("📂 Import/Export", self.open_json_manager),
        ]

        for text, command in buttons:
            btn = ctk.CTkButton(
                menu_frame,
                text=text,
                command=command,
                font=("Arial", 14),
                anchor="w",
                height=45,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("#E0E0E0", "#383838"),
                border_width=1,
                border_color=("#D0D0D0", "#404040"),
            )
            btn.pack(fill="x", padx=20, pady=5)

        theme_switch = ctk.CTkSwitch(
            menu_frame,
            text="Dark Theme",
            command=self.toggle_theme,
            font=("Arial", 12),
            progress_color="#4CC2FF",
        )
        theme_switch.pack(side="bottom", pady=20)

    # =========================
    # Main / Dashboard
    # =========================
    def show_main_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Daily progress
        progress_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            progress_frame,
            text=f"📅 Daily Progress: {self.daily_progress}/{self.daily_goal}",
            font=("Arial", 16, "bold")
        ).pack(side="left")

        progress_bar = ctk.CTkProgressBar(
            progress_frame,
            width=200,
            height=10,
            corner_radius=5,
            progress_color="#4CC2FF"
        )
        progress_bar.pack(side="left", padx=10)
        progress_bar.set(self.daily_progress / self.daily_goal if self.daily_goal else 0)

        self.update_statistics()

        # Today to learn
        today_frame = ctk.CTkFrame(
            self.content_frame,
            corner_radius=12,
            border_width=1,
            border_color=("#E0E0E0", "#383838"),
            fg_color=("#F8F8F8", "#2E2E2E")
        )
        today_frame.pack(fill="x", padx=30, pady=10)

        ctk.CTkLabel(today_frame, text="Сегодня учить", font=("Arial", 18, "bold"), pady=10)\
            .pack(anchor="w", padx=20)

        today_words = self.get_today_words()
        if today_words:
            words_list = ", ".join([w.get("word", "") for w in today_words])
            ctk.CTkLabel(today_frame, text=words_list, font=("Arial", 14), wraplength=700)\
                .pack(anchor="w", padx=20, pady=5)
        else:
            ctk.CTkLabel(today_frame, text="Добавь слова, чтобы начать", font=("Arial", 14))\
                .pack(anchor="w", padx=20, pady=5)

        start_btn = ctk.CTkButton(
            today_frame,
            text="Начать тренировку",
            width=180,
            state=("normal" if today_words else "disabled"),
            command=self.show_topic_selection
        )
        start_btn.pack(padx=20, pady=10)

        # Stats
        stats_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        stats_frame.pack(fill="both", expand=True, padx=30, pady=10)

        stats_card = ctk.CTkFrame(
            stats_frame,
            corner_radius=12,
            border_width=1,
            border_color=("#E0E0E0", "#383838"),
            fg_color=("#F8F8F8", "#333333")
        )
        stats_card.pack(fill="both", expand=True)

        ctk.CTkLabel(
            stats_card,
            text="📊 Your Statistics",
            font=("Arial", 18, "bold"),
            pady=15
        ).pack()

        grid_frame = ctk.CTkFrame(stats_card, fg_color="transparent")
        grid_frame.pack(pady=10)

        ctk.CTkLabel(grid_frame, text=f"📝 Total Words: {self.word_stats['total']}", font=("Arial", 14))\
            .grid(row=0, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkLabel(grid_frame, text=f"📅 New Today: {self.word_stats['day']}", font=("Arial", 14))\
            .grid(row=1, column=0, padx=20, pady=5, sticky="w")

        ctk.CTkLabel(grid_frame, text=f"🏆 Best Score: {self.test_stats['best_score']}%", font=("Arial", 14))\
            .grid(row=0, column=1, padx=20, pady=5, sticky="w")
        ctk.CTkLabel(grid_frame, text=f"📊 Average: {self.test_stats['average_score']}%", font=("Arial", 14))\
            .grid(row=1, column=1, padx=20, pady=5, sticky="w")

        ctk.CTkLabel(grid_frame, text=f"🔥 Streak: {self.test_stats.get('streak', 0)}", font=("Arial", 14))\
            .grid(row=0, column=2, padx=20, pady=5, sticky="w")
        ctk.CTkLabel(grid_frame, text=f"🔁 Total Reviews: {self.test_stats.get('total_reviews', 0)}", font=("Arial", 14))\
            .grid(row=1, column=2, padx=20, pady=5, sticky="w")

        best_day = self.test_stats.get("best_day")
        best_day_text = f"Best Day: {best_day['date']} ({best_day['value']})" if best_day else "Best Day: —"
        ctk.CTkLabel(grid_frame, text=best_day_text, font=("Arial", 14))\
            .grid(row=2, column=0, padx=20, pady=5, sticky="w")

        accuracy_lines = [f"{ttype}: {value}%" for ttype, value in self.test_stats.get("accuracy_by_type", {}).items()]
        accuracy_text = "; ".join(accuracy_lines) if accuracy_lines else "No practice data yet"
        ctk.CTkLabel(grid_frame, text=f"Accuracy by type: {accuracy_text}", font=("Arial", 13))\
            .grid(row=2, column=1, padx=20, pady=5, sticky="w")

        motivation_frame = ctk.CTkFrame(
            self.content_frame,
            corner_radius=12,
            border_width=1,
            border_color=("#E0E0E0", "#383838"),
            fg_color=("#F0F9FF", "#1E2A3A")
        )
        motivation_frame.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            motivation_frame,
            text=f"🔥 Words left today: {max(0, self.daily_goal - self.daily_progress)}",
            font=("Arial", 14),
            pady=10
        ).pack()

    # =========================
    # AI Chat
    # =========================
    def show_ai_chat(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        title_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        title_frame.pack(pady=10)

        ctk.CTkLabel(title_frame, text="🤖 AI Language Assistant", font=("Arial", 20, "bold")).pack()

        self.chat_display = ctk.CTkTextbox(
            self.content_frame,
            wrap="word",
            font=("Arial", 14),
            fg_color=("#444654", "#444654"),
            text_color=("#ececf1", "#ececf1"),
            state="disabled"
        )
        self.chat_display.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        input_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.user_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message here...",
            font=("Arial", 14),
            fg_color=("#565869", "#565869"),
            border_width=0
        )
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 10))

        send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_ai_message,
            width=100,
            fg_color=("#19c37d", "#19c37d"),
            hover_color=("#16a065", "#16a065"),
            font=("Arial", 14, "bold")
        )
        send_button.pack(side="right")

        back_button = ctk.CTkButton(
            self.content_frame,
            text="Back to Main",
            command=self.show_main_screen,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            font=("Arial", 12)
        )
        back_button.pack(pady=(0, 10))

        self.user_input.bind("<Return>", lambda _event: self.send_ai_message())
        self.add_ai_message("AI", "Hello! I'm your language learning assistant. How can I help you today?")

    def add_ai_message(self, sender, message):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def send_ai_message(self):
        user_message = self.user_input.get().strip()
        if not user_message:
            return

        self.user_input.delete(0, "end")
        self.add_ai_message("You", user_message)

        self.user_input.configure(state="disabled")
        self.add_ai_message("AI", "Thinking...")
        Thread(target=self.get_ai_response, args=(user_message,), daemon=True).start()

    def get_ai_response(self, user_message):
        try:
            if not self.api_key:
                self.after(0, lambda: self.update_ai_chat("Error: OPENROUTER_API_KEY is not set."))
                return

            payload = {
                "model": "deepseek/deepseek-r1:free",
                "messages": [{"role": "user", "content": user_message}]
            }

            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            ai_response = data.get("choices", [{}])[0].get("message", {}).get("content", "No response received.")
            self.after(0, lambda: self.update_ai_chat(ai_response))
        except Exception as e:
            self.after(0, lambda: self.update_ai_chat(f"Error: {str(e)}"))

    def update_ai_chat(self, response):
        self.chat_display.configure(state="normal")
        # remove last "Thinking..." line block
        try:
            self.chat_display.delete("end-2l", "end")
        except Exception:
            pass

        self.add_ai_message("AI", response)
        self.user_input.configure(state="normal")
        self.user_input.focus()

    # =========================
    # Translator
    # =========================
    def show_translator(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        title_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        title_frame.pack(pady=10)
        ctk.CTkLabel(title_frame, text="🌐 Translator", font=("Arial", 20, "bold")).pack()

        input_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        input_frame.pack(pady=10)

        ctk.CTkLabel(input_frame, text="Enter text to translate:", font=("Arial", 14)).pack(anchor="w")
        self.translate_input = ctk.CTkEntry(input_frame, width=400, font=("Arial", 14))
        self.translate_input.pack(pady=5)

        lang_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        lang_frame.pack(pady=10)

        ctk.CTkLabel(lang_frame, text="From:", font=("Arial", 14)).grid(row=0, column=0, padx=5, sticky="w")
        self.from_lang_var = ctk.StringVar(value="French")
        from_menu = ctk.CTkOptionMenu(lang_frame, variable=self.from_lang_var, values=list(self.languages.keys()), width=150)
        from_menu.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(lang_frame, text="To:", font=("Arial", 14)).grid(row=0, column=2, padx=5, sticky="w")
        self.to_lang_var = ctk.StringVar(value="Russian")
        to_menu = ctk.CTkOptionMenu(lang_frame, variable=self.to_lang_var, values=list(self.languages.keys())[1:], width=150)
        to_menu.grid(row=0, column=3, padx=5)

        translate_button = ctk.CTkButton(
            self.content_frame, text="Translate", command=self.translate_text,
            width=150, height=40, font=("Arial", 14, "bold")
        )
        translate_button.pack(pady=15)

        output_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        output_frame.pack(pady=10)

        ctk.CTkLabel(output_frame, text="Translation:", font=("Arial", 14, "bold")).pack(anchor="w")
        self.translate_output = ctk.CTkTextbox(output_frame, width=400, height=100, font=("Arial", 14),
                                               wrap="word", state="disabled")
        self.translate_output.pack(pady=5)

        copy_button = ctk.CTkButton(output_frame, text="Copy to Clipboard", command=self.copy_translation,
                                    width=150, height=30)
        copy_button.pack(pady=5)

        back_button = ctk.CTkButton(
            self.content_frame,
            text="Back to Main",
            command=self.show_main_screen,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            font=("Arial", 12)
        )
        back_button.pack(pady=10)

    def translate_text(self):
        text = self.translate_input.get().strip()
        if not text:
            return

        from_lang = self.from_lang_var.get()
        to_lang = self.to_lang_var.get()

        self.translate_output.configure(state="normal")
        self.translate_output.delete("1.0", "end")
        self.translate_output.insert("end", "Translating...")
        self.translate_output.configure(state="disabled")

        Thread(target=self.perform_translation, args=(text, from_lang, to_lang), daemon=True).start()

    def perform_translation(self, text, from_lang, to_lang):
        try:
            base_url = "https://translate.google.com/m"
            params = {"hl": self.languages[to_lang], "sl": self.languages[from_lang], "q": text}

            with httpx.Client() as client:
                response = client.get(base_url, params=params, timeout=20)
                if response.status_code != 200:
                    raise Exception("Translation service unavailable")

                soup = BeautifulSoup(response.text, "html.parser")
                result = soup.find("div", class_="result-container")
                translation = result.text if result else "Translation not found"
                self.after(0, lambda: self.display_translation(translation))

        except Exception as e:
            self.after(0, lambda: self.display_translation(f"Error: {str(e)}"))

    def display_translation(self, text):
        self.translate_output.configure(state="normal")
        self.translate_output.delete("1.0", "end")
        self.translate_output.insert("end", text)
        self.translate_output.configure(state="disabled")

    def copy_translation(self):
        text = self.translate_output.get("1.0", "end-1c")
        if text and text != "Translating..." and not text.startswith("Error:"):
            pyperclip.copy(text)

    # =========================
    # Delete Word
    # =========================
    def show_delete_word_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        title_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        title_frame.pack(pady=10)

        ctk.CTkLabel(title_frame, text="🗑️ Delete Word", font=("Arial", 20, "bold")).pack()

        search_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        search_frame.pack(pady=10)

        ctk.CTkLabel(search_frame, text="Search word to delete:", font=("Arial", 14)).pack(side="left", padx=5)

        self.delete_search_entry = ctk.CTkEntry(search_frame, width=250, font=("Arial", 14))
        self.delete_search_entry.pack(side="left", padx=5)

        search_button = ctk.CTkButton(search_frame, text="Search", command=self.search_word_to_delete, width=80)
        search_button.pack(side="left", padx=5)

        self.delete_results_frame = ctk.CTkScrollableFrame(
            self.content_frame, height=300, fg_color=("#F8F8F8", "#333333")
        )
        self.delete_results_frame.pack(fill="both", expand=True, padx=20, pady=10)

        back_button = ctk.CTkButton(
            self.content_frame,
            text="Back to Main",
            command=self.show_main_screen,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            font=("Arial", 12)
        )
        back_button.pack(pady=10)

    def search_word_to_delete(self):
        for widget in self.delete_results_frame.winfo_children():
            widget.destroy()

        search_term = self.delete_search_entry.get().strip().lower()
        if not search_term:
            return

        found_words = [
            w for w in self.words
            if search_term in w.get("word", "").lower() or search_term in w.get("translation", "").lower()
        ]

        if not found_words:
            ctk.CTkLabel(self.delete_results_frame, text="No words found matching your search", font=("Arial", 14))\
                .pack(pady=20)
            return

        for word in found_words:
            word_frame = ctk.CTkFrame(
                self.delete_results_frame, corner_radius=8, border_width=1, border_color=("#E0E0E0", "#383838")
            )
            word_frame.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(word_frame, text=f"{word['word']} - {word['translation']}", font=("Arial", 14))\
                .pack(side="left", padx=10, pady=5)

            delete_btn = ctk.CTkButton(
                word_frame, text="Delete", command=lambda w=word: self.delete_word(w),
                width=80, fg_color="#ff5555", hover_color="#cc0000"
            )
            delete_btn.pack(side="right", padx=5)

    def delete_word(self, word):
        if word in self.words:
            self.words.remove(word)
            self.save_words()
            self.word_stats["total"] = len(self.words)
        self.show_delete_word_screen()

    # =========================
    # Add Word
    # =========================
    def save_word(self, word, translation, sentence, topic="Без темы", tags_text=""):
        if not word or not translation:
            return

        tags = [t.strip() for t in (tags_text or "").split(",") if t.strip()]
        new_word = self.ensure_word_defaults({
            "word": word.capitalize(),
            "translation": translation,
            "sentence": (sentence or "").capitalize(),
            "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "review_count": 0,
            "last_reviewed": None,
            "topic": topic or "Без темы",
            "tags": tags
        })

        self.words.append(new_word)
        self.word_stats["total"] = len(self.words)
        self.word_stats["day"] += 1
        self.daily_progress += 1
        self.save_words()
        self.show_main_screen()

    def show_add_word_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        form_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        form_frame.pack(pady=50)

        ctk.CTkLabel(form_frame, text="➕ Add New Word", font=("Arial", 20, "bold"), pady=20).pack()

        ctk.CTkLabel(form_frame, text="Word:", font=("Arial", 14)).pack(pady=5)
        word_entry = ctk.CTkEntry(form_frame, width=300)
        word_entry.pack(pady=5)

        ctk.CTkLabel(form_frame, text="Translation:", font=("Arial", 14)).pack(pady=5)
        translation_entry = ctk.CTkEntry(form_frame, width=300)
        translation_entry.pack(pady=5)

        ctk.CTkLabel(form_frame, text="Example Sentence:", font=("Arial", 14)).pack(pady=5)
        sentence_entry = ctk.CTkEntry(form_frame, width=300)
        sentence_entry.pack(pady=5)

        ctk.CTkLabel(form_frame, text="Topic:", font=("Arial", 14)).pack(pady=5)
        topics = self.get_topics() or ["Без темы"]
        topic_combo = ctk.CTkComboBox(form_frame, values=topics, width=300)
        topic_combo.set(topics[0])
        topic_combo.pack(pady=5)

        new_topic_entry = ctk.CTkEntry(form_frame, width=300, placeholder_text="New topic (optional)")
        new_topic_entry.pack(pady=5)

        ctk.CTkLabel(form_frame, text="Tags (comma separated):", font=("Arial", 14)).pack(pady=5)
        tags_entry = ctk.CTkEntry(form_frame, width=300, placeholder_text="travel, food, verbs")
        tags_entry.pack(pady=5)

        button_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        button_frame.pack(pady=20)

        ctk.CTkButton(
            button_frame,
            text="Save",
            command=lambda: self.save_word(
                word_entry.get(),
                translation_entry.get(),
                sentence_entry.get(),
                (new_topic_entry.get().strip() or topic_combo.get()),
                tags_entry.get()
            ),
            width=120
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_frame,
            text="Back",
            command=self.show_main_screen,
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040")
        ).pack(side="left", padx=10)

    # =========================
    # Search
    # =========================
    def show_search_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        search_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        search_frame.pack(pady=20)

        ctk.CTkLabel(search_frame, text="🔍 Search Word", font=("Arial", 20, "bold"), pady=10).pack()

        search_entry = ctk.CTkEntry(search_frame, width=300, placeholder_text="Enter word to search...")
        search_entry.pack(pady=10)

        ctk.CTkButton(
            search_frame,
            text="Search",
            command=lambda: self.perform_search(search_entry.get()),
            width=120
        ).pack(pady=5)

        ctk.CTkButton(
            search_frame,
            text="Back",
            command=self.show_main_screen,
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040")
        ).pack(pady=5)

        self.search_results_frame = ctk.CTkScrollableFrame(self.content_frame, height=300)
        self.search_results_frame.pack(fill="both", expand=True, padx=30, pady=10)

    def perform_search(self, search_term):
        for widget in self.search_results_frame.winfo_children():
            widget.destroy()

        if not search_term:
            ctk.CTkLabel(self.search_results_frame, text="Please enter a search term", font=("Arial", 14))\
                .pack(pady=10)
            return

        search_term = search_term.lower()
        found = False

        for word in self.words:
            if (search_term in word.get("word", "").lower() or
                    search_term in word.get("translation", "").lower() or
                    (word.get("sentence") and search_term in word.get("sentence", "").lower())):
                found = True
                self.display_search_result(word)

        for filename in os.listdir("logs"):
            if filename.endswith(".json") and filename != "user_words.json":
                try:
                    with open(os.path.join("logs", filename), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    if (search_term in item.get("word", "").lower() or
                                            search_term in item.get("translation", "").lower() or
                                            search_term in item.get("sentence", "").lower()):
                                        found = True
                                        self.display_search_result(item)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

        if not found:
            ctk.CTkLabel(self.search_results_frame, text=f"No results found for '{search_term}'", font=("Arial", 14))\
                .pack(pady=10)

    def display_search_result(self, word_data):
        result_frame = ctk.CTkFrame(
            self.search_results_frame,
            corner_radius=8,
            border_width=1,
            border_color=("#E0E0E0", "#383838")
        )
        result_frame.pack(fill="x", pady=5, padx=5)

        ctk.CTkLabel(
            result_frame,
            text=f"{word_data.get('word', 'N/A')} - {word_data.get('translation', 'N/A')}",
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=10, pady=5)

        if word_data.get("sentence"):
            ctk.CTkLabel(result_frame, text=f"Example: {word_data['sentence']}", font=("Arial", 12))\
                .pack(anchor="w", padx=10, pady=2)

        if word_data.get("date_added"):
            ctk.CTkLabel(
                result_frame,
                text=f"Added: {word_data['date_added']}",
                font=("Arial", 10),
                text_color=("gray50", "gray70")
            ).pack(anchor="w", padx=10, pady=2)

    # =========================
    # All Words + Filters
    # =========================
    def show_all_words(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        all_words_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        all_words_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(all_words_frame, text="📖 All Words", font=("Arial", 20, "bold"), pady=10).pack()

        filter_frame = ctk.CTkFrame(all_words_frame, fg_color=("#F8F8F8", "#2E2E2E"))
        filter_frame.pack(fill="x", pady=10)

        self.current_topic_filter = getattr(self, "current_topic_filter", "")
        self.current_tag_filter = getattr(self, "current_tag_filter", "")
        self.current_status_filter = getattr(self, "current_status_filter", "")
        self.current_search_filter = getattr(self, "current_search_filter", "")

        topics = ["All"] + self.get_topics()
        ctk.CTkLabel(filter_frame, text="Topic", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=5)
        topic_combo = ctk.CTkComboBox(
            filter_frame,
            values=topics,
            width=160,
            command=lambda _v: self.apply_filters(topic_combo, tag_entry, status_combo, search_entry)
        )
        topic_combo.set(self.current_topic_filter or topics[0])
        topic_combo.grid(row=1, column=0, padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Tag", font=("Arial", 12)).grid(row=0, column=1, padx=5, pady=5)
        tag_entry = ctk.CTkEntry(filter_frame, width=160)
        tag_entry.insert(0, self.current_tag_filter)
        tag_entry.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Status", font=("Arial", 12)).grid(row=0, column=2, padx=5, pady=5)
        status_combo = ctk.CTkComboBox(
            filter_frame,
            values=["All", "New", "Learning", "Mastered"],
            width=160,
            command=lambda _v: self.apply_filters(topic_combo, tag_entry, status_combo, search_entry)
        )
        status_combo.set(self.current_status_filter or "All")
        status_combo.grid(row=1, column=2, padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Search", font=("Arial", 12)).grid(row=0, column=3, padx=5, pady=5)
        search_entry = ctk.CTkEntry(filter_frame, width=180)
        search_entry.insert(0, self.current_search_filter)
        search_entry.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkButton(
            filter_frame,
            text="Apply",
            width=120,
            command=lambda: self.apply_filters(topic_combo, tag_entry, status_combo, search_entry)
        ).grid(row=1, column=4, padx=10, pady=5)

        ctk.CTkButton(filter_frame, text="Reset", width=120, command=self.reset_filters)\
            .grid(row=1, column=5, padx=10, pady=5)

        self.words_list_frame = ctk.CTkScrollableFrame(all_words_frame, height=400, fg_color=("#F8F8F8", "#333333"))
        self.words_list_frame.pack(fill="both", expand=True)

        ctk.CTkButton(
            all_words_frame,
            text="Back to Main",
            command=self.show_main_screen,
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            font=("Arial", 12)
        ).pack(pady=10)

        self.display_all_words()

    def display_all_words(self):
        for widget in self.words_list_frame.winfo_children():
            widget.destroy()

        if not self.words:
            ctk.CTkLabel(self.words_list_frame, text="Your word list is empty", font=("Arial", 14))\
                .pack(pady=20)
            return

        filtered_words = self.words[:]
        topic = getattr(self, "current_topic_filter", "")
        tag = getattr(self, "current_tag_filter", "")
        status = getattr(self, "current_status_filter", "")
        search = getattr(self, "current_search_filter", "").lower()

        if topic and topic != "All":
            filtered_words = [w for w in filtered_words if w.get("topic", "Без темы") == topic]
        if tag:
            filtered_words = [w for w in filtered_words if tag.lower() in [t.lower() for t in w.get("tags", [])]]
        if status and status != "All":
            filtered_words = [w for w in filtered_words if w.get("status", "New") == status]
        if search:
            filtered_words = [
                w for w in filtered_words
                if search in w.get("word", "").lower() or search in w.get("translation", "").lower()
            ]

        for word in filtered_words:
            word_frame = ctk.CTkFrame(
                self.words_list_frame, corner_radius=8, border_width=1, border_color=("#E0E0E0", "#383838")
            )
            word_frame.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(word_frame, text=f"{word['word']} - {word['translation']}", font=("Arial", 14))\
                .pack(anchor="w", padx=10, pady=5)

            meta_text = f"Topic: {word.get('topic', 'Без темы')} | Status: {word.get('status', 'New')}"
            ctk.CTkLabel(word_frame, text=meta_text, font=("Arial", 12), text_color=("gray60", "gray70"))\
                .pack(anchor="w", padx=10)

            if word.get("tags"):
                ctk.CTkLabel(word_frame, text=f"Tags: {', '.join(word.get('tags', []))}", font=("Arial", 12))\
                    .pack(anchor="w", padx=10)

            if word.get("sentence"):
                ctk.CTkLabel(
                    word_frame,
                    text=f"Example: {word['sentence']}",
                    font=("Arial", 12),
                    text_color=("gray50", "gray70")
                ).pack(anchor="w", padx=10, pady=2)

    def apply_filters(self, topic_combo, tag_entry, status_combo, search_entry):
        self.current_topic_filter = topic_combo.get()
        self.current_tag_filter = tag_entry.get().strip()
        self.current_status_filter = status_combo.get()
        self.current_search_filter = search_entry.get().strip()
        self.display_all_words()

    def reset_filters(self):
        self.current_topic_filter = "All"
        self.current_tag_filter = ""
        self.current_status_filter = "All"
        self.current_search_filter = ""
        self.show_all_words()

    # =========================
    # Topics screen
    # =========================
    def show_topics_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="🏷️ Topics", font=("Arial", 20, "bold"), pady=10).pack()

        topics_data = {}
        for w in self.words:
            topics_data.setdefault(w.get("topic", "Без темы"), []).append(w)

        list_frame = ctk.CTkScrollableFrame(frame, height=400)
        list_frame.pack(fill="both", expand=True, pady=10)

        for topic, items in topics_data.items():
            row = ctk.CTkFrame(list_frame, corner_radius=8, border_width=1, border_color=("#E0E0E0", "#383838"))
            row.pack(fill="x", pady=4, padx=4)

            ctk.CTkLabel(row, text=f"{topic} ({len(items)} words)", font=("Arial", 14, "bold"))\
                .pack(side="left", padx=10)

            rename_entry = ctk.CTkEntry(row, width=180, placeholder_text="Rename")
            rename_entry.pack(side="left", padx=5)

            ctk.CTkButton(
                row,
                text="Rename",
                width=80,
                command=lambda t=topic, e=rename_entry: self.rename_topic(t, e.get().strip())
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                row,
                text="Delete",
                fg_color="#ff5555",
                hover_color="#cc0000",
                width=80,
                command=lambda t=topic: self.delete_topic(t)
            ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame,
            text="Back",
            command=self.show_main_screen,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            width=140
        ).pack(pady=10)

    def rename_topic(self, old_topic, new_topic):
        if not new_topic:
            return
        for w in self.words:
            if w.get("topic", "Без темы") == old_topic:
                w["topic"] = new_topic
        self.save_words()
        self.show_topics_screen()

    def delete_topic(self, topic):
        for w in self.words:
            if w.get("topic", "Без темы") == topic:
                w["topic"] = "Без темы"
        self.save_words()
        self.show_topics_screen()

    # =========================
    # Topic selection + Quiz
    # =========================
    def show_topic_selection(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        selection_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        selection_frame.pack(fill="both", expand=True, padx=30, pady=30)

        ctk.CTkLabel(selection_frame, text="Выберите тему для квиза", font=("Arial", 18, "bold"))\
            .pack(pady=(0, 20))

        topics = ["Все темы"] + self.get_topics()
        topics = list(dict.fromkeys(topics))
        initial_topic = self.last_selected_topic if self.last_selected_topic in topics else "Все темы"

        info_label = ctk.CTkLabel(selection_frame, text="", font=("Arial", 13))
        info_label.pack(pady=5)

        start_button = ctk.CTkButton(
            selection_frame,
            text="Начать квиз",
            width=180,
            command=lambda: self.start_test(selected_topic=topic_combo.get())
        )
        start_button.pack(pady=15)

        def update_state():
            selected = topic_combo.get()
            available_words = self.get_words_for_quiz(selected)
            if available_words:
                start_button.configure(state="normal")
                info_label.configure(text=f"Слов в теме: {len(available_words)}")
            else:
                start_button.configure(state="disabled")
                info_label.configure(text="В теме нет слов")

        topic_combo = ctk.CTkComboBox(
            selection_frame,
            values=topics,
            state="readonly",
            width=240,
            font=("Arial", 14),
            command=lambda _v: update_state()
        )
        topic_combo.set(initial_topic)
        topic_combo.pack(pady=10)

        ctk.CTkButton(
            selection_frame,
            text="Назад",
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            command=self.show_main_screen
        ).pack(pady=5)

        update_state()

    def start_test(self, selected_words=None, selected_topic="Все темы"):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        target_words = selected_words if selected_words is not None else self.get_words_for_quiz(selected_topic)
        self.last_selected_topic = selected_topic

        if not target_words:
            ctk.CTkLabel(self.content_frame, text="No words available for testing. Add some words first!",
                         font=("Arial", 16)).pack(pady=50)
            ctk.CTkButton(
                self.content_frame,
                text="Back to Main",
                command=self.show_main_screen,
                width=120,
                fg_color="transparent",
                border_width=1,
                border_color=("#D0D0D0", "#404040"),
                font=("Arial", 12)
            ).pack(pady=10)
            return

        self.test_words = random.sample(target_words, min(10, len(target_words)))
        self.current_test_index = 0
        self.correct_answers = 0

        test_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        test_frame.pack(fill="both", expand=True, padx=30, pady=30)

        ctk.CTkLabel(test_frame, text=f"Practice — Тема: {selected_topic}", font=("Arial", 18, "bold"))\
            .pack(pady=(0, 10))

        self.question_label = ctk.CTkLabel(test_frame, text="", font=("Arial", 18, "bold"), wraplength=500)
        self.question_label.pack(pady=20)

        self.answer_entry = ctk.CTkEntry(test_frame, width=300, font=("Arial", 14),
                                         placeholder_text="Type your answer...")
        self.answer_entry.pack(pady=10)

        submit_button = ctk.CTkButton(test_frame, text="Submit", command=self.check_test_answer,
                                      width=120, font=("Arial", 14))
        submit_button.pack(pady=10)

        self.progress_label = ctk.CTkLabel(test_frame, text=f"Question 1 of {len(self.test_words)}",
                                           font=("Arial", 12))
        self.progress_label.pack(pady=5)

        back_button = ctk.CTkButton(
            test_frame,
            text="Cancel Test",
            command=self.show_main_screen,
            fg_color="transparent",
            border_width=1,
            border_color=("#D0D0D0", "#404040"),
            font=("Arial", 12)
        )
        back_button.pack(pady=10)

        self.show_next_test_question()

    def show_next_test_question(self):
        if self.current_test_index >= len(self.test_words):
            self.show_test_results()
            return

        current_word = self.test_words[self.current_test_index]

        if random.choice([True, False]):
            self.question_label.configure(text=f"What is the translation of: '{current_word['word']}'?")
            self.correct_answer = current_word["translation"]
        else:
            self.question_label.configure(text=f"What is the word for: '{current_word['translation']}'?")
            self.correct_answer = current_word["word"]

        self.progress_label.configure(text=f"Question {self.current_test_index + 1} of {len(self.test_words)}")
        self.answer_entry.delete(0, "end")

    def check_test_answer(self):
        user_answer = self.answer_entry.get().strip()
        if not user_answer:
            return

        current_word = self.test_words[self.current_test_index]
        if user_answer.lower() == self.correct_answer.lower():
            self.correct_answers += 1
            current_word["review_count"] = current_word.get("review_count", 0) + 1
            current_word["status"] = "Learning" if current_word["review_count"] < 3 else "Mastered"
            correct = True
        else:
            current_word["status"] = current_word.get("status", "New")
            correct = False

        self.log_review(current_word, correct, test_type="practice")
        self.save_words()

        self.current_test_index += 1
        self.show_next_test_question()

    def show_test_results(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        score = int((self.correct_answers / len(self.test_words)) * 100) if self.test_words else 0

        if score > self.test_stats["best_score"]:
            self.test_stats["best_score"] = score
        if self.test_stats["average_score"] == 0:
            self.test_stats["average_score"] = score
        else:
            self.test_stats["average_score"] = (self.test_stats["average_score"] + score) // 2

        results_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        results_frame.pack(fill="both", expand=True, padx=30, pady=30)

        if score >= 80:
            result_text = "🎉 Excellent! 🎉"
            color = "#4CC2FF"
        elif score >= 60:
            result_text = "👍 Good job! 👍"
            color = "#4CC2FF"
        else:
            result_text = "Keep practicing!"
            color = "#FF5555"

        ctk.CTkLabel(results_frame, text="Practice Results", font=("Arial", 24, "bold"), pady=20).pack()
        ctk.CTkLabel(results_frame, text=f"You scored: {score}%", font=("Arial", 20), text_color=color)\
            .pack(pady=10)
        ctk.CTkLabel(results_frame, text=f"{self.correct_answers} correct out of {len(self.test_words)}",
                     font=("Arial", 16)).pack(pady=5)
        ctk.CTkLabel(results_frame, text=result_text, font=("Arial", 18), text_color=color).pack(pady=20)

        ctk.CTkButton(results_frame, text="Back to Main", command=self.show_main_screen,
                      width=150, font=("Arial", 14)).pack(pady=20)

    # =========================
    # Misc
    # =========================
    def open_json_manager(self):
        print("Import/Export will be implemented here")

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if current == "dark" else "dark")

    # =========================
    # Statistics
    # =========================
    def update_statistics(self):
        self.test_stats["total_reviews"] = len(self.training_history)

        daily_correct = {}
        for entry in self.training_history:
            if entry.get("result") == "correct":
                d = entry.get("date")
                if d:
                    daily_correct[d] = daily_correct.get(d, 0) + 1

        # Streak: consecutive days from today backwards, where correct >= daily_goal
        streak = 0
        today = datetime.now().date()
        for i in range(0, 365):  # max lookback
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if daily_correct.get(day, 0) >= self.daily_goal:
                streak += 1
            else:
                break
        self.test_stats["streak"] = streak

        if daily_correct:
            best_day = max(daily_correct.items(), key=lambda kv: kv[1])
            self.test_stats["best_day"] = {"date": best_day[0], "value": best_day[1]}
        else:
            self.test_stats["best_day"] = None

        counts = {}
        for entry in self.training_history:
            ttype = entry.get("testType", "practice")
            counts.setdefault(ttype, {"correct": 0, "total": 0})
            counts[ttype]["total"] += 1
            if entry.get("result") == "correct":
                counts[ttype]["correct"] += 1

        accuracy = {}
        for ttype, vals in counts.items():
            accuracy[ttype] = int((vals["correct"] / vals["total"]) * 100) if vals["total"] else 0
        self.test_stats["accuracy_by_type"] = accuracy


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
