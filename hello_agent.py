
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour


class HelloAgent(Agent):

    class HelloBehaviour(OneShotBehaviour):
        async def run(self):
            print(f"Olá! Sou o agente {self.agent.jid}")

    async def setup(self):
        print("A iniciar o agente...")
        self.behaviour = self.HelloBehaviour()
        self.add_behaviour(self.behaviour)


async def main():
    agent = HelloAgent("teste_isia@localhost", "password-local")

    await agent.start(auto_register=True)

    try:
        await agent.behaviour.join()
    finally:
        await agent.stop()

    print("Agente terminou corretamente.")


if __name__ == "__main__":
    spade.run(main())
