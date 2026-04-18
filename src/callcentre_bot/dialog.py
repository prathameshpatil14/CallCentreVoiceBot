from dataclasses import dataclass

from .knowledge import find_faq_answer, find_product
from .sentiment import Sentiment


@dataclass
class BotReply:
    text: str
    escalate_to_human: bool = False


class DialogPolicy:
    def respond(self, user_text: str, sentiment: Sentiment) -> BotReply:
        text = user_text.lower().strip()

        if sentiment == "negative":
            apology = "I am sorry this has been frustrating. "
        else:
            apology = ""

        faq_answer = find_faq_answer(text)
        if faq_answer:
            return BotReply(text=f"{apology}{faq_answer} Is there anything else I can help with?")

        product = find_product(text)
        if product:
            return BotReply(
                text=(
                    f"{apology}Great choice. {product.name} is {product.price}. "
                    f"{product.pitch} Would you like me to start your purchase now?"
                )
            )

        if any(word in text for word in ["agent", "human", "representative", "complaint"]):
            return BotReply(
                text=(
                    f"{apology}I can connect you to a human specialist right away. "
                    "Please hold while I transfer your call."
                ),
                escalate_to_human=True,
            )

        if "buy" in text or "purchase" in text or "plan" in text:
            options = "Premium Broadband, Family Mobile Plan, and Smart Home Security"
            return BotReply(text=f"{apology}I can help you choose. Our top products are: {options}.")

        return BotReply(
            text=(
                f"{apology}I want to make sure I understand. "
                "Can you share if this is about billing, technical support, cancellation, or buying a new product?"
            )
        )
