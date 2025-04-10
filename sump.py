import re
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

class NewsProcessor:
    def __init__(self):
        self.model_name = "DeepPavlov/rubert-base-cased"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        # Ключевые слова для определения "интересности" новостей
        # Добавлены валютные обозначения для сохранения важных фактов
        self.keywords = {
            'экономика', 'рынок', 'инвестиции', 'акции', 'биржа',
            'инфляция', 'кризис', 'валюта', 'нефть', 'технологии',
            'usd', 'eur', 'rub', 'cny'
        }

    def _split_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения с учетом минимальной длины.
        """
        sentences = re.split(
            r'(?<!\w\.\w.)(?<![A-ZА-Я][a-zа-я]\.)(?<=[.!?])\s+',
            text
        )
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Получает эмбеддинги для списка текстов.
        """
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        return self._mean_pooling(outputs, inputs['attention_mask']).cpu().numpy()

    def _mean_pooling(self, model_output, attention_mask):
        """
        Применяет усреднение эмбеддингов с учетом маски.
        """
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def _calculate_interest_score(self, text: str) -> float:
        """
        Рассчитывает оценку "интересности" текста (как для всей новости, так и для отдельного предложения).
        Составляющие:
          - keyword_count: количество ключевых слов
          - length_score: оценка по длине (максимум = 1)
          - number_count: количество числовых показателей
          - emotion_score: количество эмоционально окрашенных слов
        Итоговый балл – взвешенная сумма (коэффициенты можно подбирать экспериментально).
        """
        # 1. Количество ключевых слов
        keyword_count = sum(1 for word in text.lower().split() if word in self.keywords)
        # 2. Длина текста (нормализована до 1 при длине 1000 символов)
        length_score = min(len(text) / 1000, 1.0)
        # 3. Наличие чисел (финансовых показателей)
        number_count = len(re.findall(r'\d+', text))
        # 4. Эмоциональная окраска
        emotional_words = {'рост', 'падение', 'кризис', 'прорыв', 'рекорд'}
        emotion_score = sum(1 for word in text.lower().split() if word in emotional_words)
        
        return (keyword_count * 0.4 + length_score * 0.2 + 
                number_count * 0.2 + emotion_score * 0.2)

    def _remove_duplicates(self, news_list: List[Dict], threshold: float = 0.85) -> List[Dict]:
        """
        Удаляет дубликаты из списка новостей, используя косинусное сходство эмбеддингов.
        Если сходство между двумя новостями выше порога, считается, что они дублируются.
        """
        if len(news_list) < 2:
            return news_list
            
        embeddings = np.array([item['embedding'] for item in news_list])
        similarity_matrix = cosine_similarity(embeddings)
        
        duplicates = set()
        for i in range(len(similarity_matrix)):
            for j in range(i+1, len(similarity_matrix)):
                if similarity_matrix[i][j] > threshold:
                    duplicates.add(j)
        
        return [item for idx, item in enumerate(news_list) if idx not in duplicates]

    def process_news(self, news_texts: List[str], top_n: int = 5, sentences_in_summary: int = 3) -> List[List[str]]:
        """
        Обрабатывает список новостей:
          1. Суммаризация с подбором наиболее "интересных" предложений.
             Для каждого текста:
             - Разбиваем текст на предложения.
             - Вычисляем баллы для каждого предложения.
             - Выбираем top_K предложений с наивысшим баллом и сортируем по порядку, как в исходном тексте.
          2. Получение эмбеддингов для суммаризации.
          3. Расчет "интересности" для каждой новости (на основе суммаризации).
          4. Удаление дубликатов.
          5. Ранжирование по интересности.
          6. Разделение на группы по top_n новостей для формирования постов.
          
        :param news_texts: Список исходных новостных сообщений.
        :param top_n: Максимальное число новостей в одном посте.
        :param sentences_in_summary: Количество предложений, которые будут включены в суммаризацию каждой новости.
        :return: Список групп (постов), где каждая группа – список строк с нумерацией.
        """
        processed_news = []
        for text in news_texts:
            sentences = self._split_sentences(text)
            if not sentences:
                continue

            # Вычисляем балл для каждого предложения
            sentence_scores = [(idx, self._calculate_interest_score(sentence)) 
                               for idx, sentence in enumerate(sentences)]
            # Выбираем предложения с наивысшим баллом
            top_sentences = sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:sentences_in_summary]
            # Сортируем выбранные предложения по их исходному порядку
            top_sentences = sorted(top_sentences, key=lambda x: x[0])
            summary = ' '.join([sentences[idx] for idx, _ in top_sentences])
            # Получаем эмбеддинг суммаризации
            embedding = self._get_embeddings([summary])[0]
            
            processed_news.append({
                'text': summary,
                'embedding': embedding,
                'score': self._calculate_interest_score(summary)
            })
        
        # Удаляем дубликаты
        unique_news = self._remove_duplicates(processed_news)
        # Ранжируем по интересности (от высоких баллов к низким)
        sorted_news = sorted(unique_news, key=lambda x: x['score'], reverse=True)
        
        # Группируем новости в посты (каждый пост – список новостей)
        grouped_news = []
        for i in range(0, len(sorted_news), top_n):
            group = sorted_news[i:i+top_n]
            formatted_group = [
                f"📌 {idx+1}. {item['text']}" 
                for idx, item in enumerate(group)
            ]
            grouped_news.append(formatted_group)
        
        return grouped_news

if __name__ == "__main__":
    # Пример использования NewsProcessor
    processor = NewsProcessor()
    
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
    
    # Обработка новостей с разделением на посты (максимум 5 новостей в одном посте, суммаризация - 3 предложения)
    grouped_posts = processor.process_news(sample_news, top_n=5, sentences_in_summary=3)
    
    print("Группированные новости для отправки:")
    for idx, group in enumerate(grouped_posts, start=1):
        print(f"\nПост {idx}:")
        for line in group:
            print(line)
