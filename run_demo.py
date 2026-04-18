from callcentre_bot import VoiceSalesAssistant


def main() -> None:
    print("CallCentreVoiceBot demo. Type 'exit' to stop.\n")
    bot = VoiceSalesAssistant()

    while True:
        user_input = input("Customer: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Bot: Thank you for calling. Goodbye.")
            break

        reply = bot.handle_text(user_input)
        print(f"Bot: {reply.text}")

        if reply.escalate_to_human:
            print("[System] Escalation flag raised: transfer to human agent queue.")
            break


if __name__ == "__main__":
    main()
