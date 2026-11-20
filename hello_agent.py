"""Teste mínimo de instalação: um agente SPADE que se apresenta e termina."""

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour


class HelloAgent(Agent):
    """Agente de teste com um único comportamento de execução única.

    Attributes:
        behaviour (HelloAgent.HelloBehaviour): Comportamento criado em ``setup``; main
            espera pelo seu fim.
    """

    class HelloBehaviour(OneShotBehaviour):
        """Comportamento que imprime a saudação uma vez e termina."""
        async def run(self):
            """Imprimir a saudação com o JID do agente.

            Overrides:
                spade.behaviour.OneShotBehaviour.run
            """
            print(f"Olá! Sou o agente {self.agent.jid}")

    async def setup(self):
        """Criar o comportamento e guardá-lo em ``self.behaviour``, que main aguarda.

        Overrides:
            spade.agent.Agent.setup
        """
        print("A iniciar o agente...")
        self.behaviour = self.HelloBehaviour()
        self.add_behaviour(self.behaviour)


async def main():
    """Iniciar o agente, esperar pelo fim do comportamento e parar o agente sempre."""
    agent = HelloAgent("teste_isia@localhost", "password-local")

    await agent.start(auto_register=True)

    try:
        await agent.behaviour.join()
    finally:
        await agent.stop()

    print("Agente terminou corretamente.")


if __name__ == "__main__":
    spade.run(main())
