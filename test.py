import textwrap
import requests
from sump import NewsProcessor
from typing import List
import re

class EnhancedNewsProcessor(NewsProcessor):
    def _split_sentences(self, text: str) -> List[str]:
        """Улучшенная обработка текста с очисткой от мусора"""
        # Удаляем URL и спецсимволы
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[■•&]', ' ', text)
        
        sentences = re.split(
            r'(?<!\w\.\w.)(?<![A-ZА-Я][a-zа-я]\.)(?<=[.!?])\s+',
            text
        )
        return [s.strip() for s in sentences if 20 < len(s.strip()) < 500]

    def _calculate_interest_score(self, text: str) -> float:
        """Улучшенная система оценки с приоритетом чисел и показателей"""
        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # 1. Ключевые слова (увеличили вес)
        keyword_count = sum(1 for word in self.keywords if re.search(rf'\b{word}\b', text.lower()))
        
        # 2. Наличие финансовых показателей
        number_count = len(re.findall(r'\b\d+[\.,]\d+\b', text))
        
        # 3. Длина текста (меньший вес)
        length_score = min(len(text) / 400, 1.0)  # Нормализация до 400 символов
        
        # 4. Важные сущности
        entity_score = len(re.findall(
            r'\b(USD|EUR|RUB|нефть|газ|акции|дивиденды|прибыль|кредит)\b', 
            text, 
            flags=re.IGNORECASE
        ))
        
        return (keyword_count * 0.5 + 
                number_count * 0.3 + 
                entity_score * 0.2 + 
                length_score * 0.1)

class MistralAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    def generate(self, prompt: str, model: str = "mistral-medium") -> str:
        data = {
            "model": model,
            "messages": [{
                "role": "system",
                "content": "Вы senior финансовый аналитик. Кратко выдели 3 главных вывода на русском. Только факты."
            }, {
                "role": "user",
                "content": f"Новости:\n{prompt}\n\nАнализ:"
            }],
            "temperature": 0.2,
            "max_tokens": 300
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=data,
                headers=self.headers,
                timeout=20  # Увеличили таймаут
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Ошибка API: {e}")
            return "Анализ недоступен. Рекомендуем проверить подключение."

class ReportGenerator:
    def __init__(self, api_key: str):
        self.mistral = MistralAPI(api_key)
    
    def _format_prompt(self, grouped_posts: List[List[str]]) -> str:
        """Формируем компактный промпт"""
        return "\n\n".join(
            f"Новость {i+1}: " + " ".join(g[:300] for g in group) 
            for i, group in enumerate(grouped_posts)
        )[:3000]  # Ограничение длины промпта

    def generate_report(self, grouped_posts: List[List[str]]) -> str:
        report = [
            "═" * 60,
            "ФИНАНСОВЫЙ БЮЛЛЕТЕНЬ".center(60),
            "═" * 60,
            ""
        ]
        
        for idx, group in enumerate(grouped_posts, 1):
            report.append(f"▌ Блок {idx} ▌".center(60, "─"))
            for item in group:
                # Упрощаем форматирование
                clean_text = re.sub(r'\s+', ' ', item.split(".", 1)[-1].strip())
                wrapped = textwrap.fill(
                    f"→ {clean_text[:250]}", 
                    width=58,
                    initial_indent="  ",
                    subsequent_indent="    "
                )
                report.append(wrapped)
            report.append("")
        
        # Генерация выводов
        report.extend([
            "═" * 60,
            "КЛЮЧЕВЫЕ ВЫВОДЫ:".ljust(60),
            self.mistral.generate(self._format_prompt(grouped_posts)),
            "",
            "Отчет сгенерирован автоматически".center(60),
            "═" * 60
        ])
        
        return "\n".join(report)

def main():
    processor = EnhancedNewsProcessor()  # Используем улучшенный процессор
    api_key = "qOD6O33rZUL7pAHzJnMZx5jD1MuttwSs"
    
    sample_news = [
        '''Московская биржа запустила фьючерсы на природный газ Dutch TTF
В последнее время запасы газа в Европе находятся на минимальных уровнях за три года, что в том числе отражается на цене топлива на европейских биржах. Геополитическая обстановка давит на Еврозону, а полный отказ от российского газа может взвинтить цены на горючее. С помощью новых контрактов можно зарабатывать на цене газа в европейском газовом хабе.
DUTCH TTF NATURAL GAS — самая активная газовая биржа в Европе с объемом торговли около 20 трлн кубических метров топлива. Голландский TTF Gas — ведущая европейская эталонная цена, поскольку объемы торгов более чем в 14 раз превышают объемы газа, используемого Нидерландами для внутренних целей.
Расчетные фьючерсы на европейский газ помогут быстро получить финансовый результат за счет изменения цен на топливо. Если вы рассчитываете, что цены будут снижаться, контракт можно шортить. Если же считаете, что котировки будут расти — фьючерсы можно купить.''',
        '''Утренний дайджест: торговые войны и цены на нефть, данные по инфляции в России
На что стоит обратить внимание сегодня, 09.04.2025
Компании:
• Сбербанк: публикация финансовых результатов по РПБУ за март и три месяца 2025 года.
• Аэрофлот: заседание совета директоров. На повестке вопрос выплаты дивидендов за 2024 год.
Валютные курсы (ЦБ РФ):
USD/RUB: 85,46 (-0,84%).
EUR/RUB: 93,78 (-1,05%).
CNY/RUB: 11,57 (-1,38%).
Товарно-сырьевой рынок:
Urals: 53,66 (-2,08%).
Brent: 60,20 (-1,73%).
Золото: 3 014,86 (+1,09%).
Газ: 3,496 (+0,89%).
Дополнительно:
• В ходе торгов стоимость нефти марки Brent упала ниже $61 за баррель впервые с марта 2021 года. Эксперты связывают динамику с торговыми войнами и мировыми санкциями.''',
        '''Сбербанк опубликовал (https://www.sberbank.ru/ru/sberpress/vazhnoe/article?newsID=3af08b0a-4cfb-4a9e-97aa-e3a0f968bb6f&blockID=8a5ea25e-318c-4d17-a60d-e806c4b0bc07&regionID=22&lang=ru&type=NEWS) отчет РПБУ за март и первые три месяца 2025 года. Чистая прибыль продолжает расти, а рентабельность капитала в первом квартале составила 22,6%. Розничный кредитный портфель Сбера вырос на 0,3% за счет ипотечного кредитования и кредитных карт. На 1% подрос корпоративный кредитный портфель.'''
    ]
    
    grouped_posts = processor.process_news(
        sample_news,
        top_n=2,
        sentences_in_summary=2  # Более короткие суммаризации
    )
    
    report = ReportGenerator(api_key).generate_report(grouped_posts)
    print(report)

if __name__ == "__main__":
    main()