# PLC-Fundamentos

Programação estruturada básica de PLC no TwinCAT 3: variáveis, temporizadores, lógica de controle simples — sem foco em comunicação, motion ou HMI.

## Projetos

- **[PLC](PLC/)** — simulação de dois reservatórios com bomba (`Nivel1`, `Nivel2`, `BombaAtiva`) usando `TON`. Par didático do supervisório em [`HMI-Supervisorio/ExemploSupervisório`](../HMI-Supervisorio/ExemploSupervisório/).
- **[TutorialControleRefrigerador](TutorialControleRefrigerador/)** — controle de refrigerador por histerese em CFC (comparadores GT/LT + flip-flop SR), com POU de alarmes e simulação.

## Possíveis assuntos futuros

- Máquinas de estado (state machines) genéricas
- Temporizadores/contadores avançados (TON/TOF/RTC combinados, debounce)
- Testes unitários de PLC com TcUnit
