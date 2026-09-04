# Exercícios de Motion Control — Trilha de Preparação para a Certificação

Esta pasta contém uma trilha progressiva de exercícios práticos usando a biblioteca **Tc2_MC2** (blocos
`MC_*` no padrão PLCopen), a mesma biblioteca já usada no projeto [`MotionControl`](../MotionControl/).
O objetivo é treinar, em blocos pequenos e isolados, todos os conceitos que caem na **PROVA PRÁTICA de
certificação de Motion**, culminando em um simulado completo no Nível 4.
Os arquivos de projeto dos programas resolvendo os exercícios foram feitos como simulação local (TwinCAT 3 4026.26 + User Mode Runtime).

## Como usar

1. Abra o projeto [`MotionControl.sln`](../MotionControl/MotionControl.sln) no TwinCAT XAE Shell / Visual
   Studio. Ele já tem a biblioteca `Tc2_MC2` referenciada e dois eixos NC configurados
   (`GVL_Axes.Axis1` e `GVL_Axes.Axis2`), simulados em software (não precisa de hardware real).
2. Para cada exercício, leia o `README.md` da pasta correspondente — ele descreve o cenário, os
   blocos `MC_*` que devem ser usados e os critérios de aceite.
3. Tente resolver **antes de olhar o gabarito**: crie seu próprio POU (`PRG_ExNN_...`) dentro do
   projeto, implemente a lógica pedida e chame-o a partir do `MAIN`.
4. Só depois compare com o arquivo `Gabarito.TcPOU` da pasta — copie-o para dentro do projeto
   (botão direito em `POUs` → *Add* → *Existing Item...*) ou apenas leia o texto comentado.
5. Ajuste as escalas dos eixos (`_Config/NC/Axes/Axis 1.xti` e `Axis 2.xti`) conforme pedido em
   cada exercício antes de testar em modo Free-Run/simulação.

## Estrutura da trilha

| Nível | Pasta | Foco | Blocos `MC_*` |
|---|---|---|---|
| 1 — Básico | [`Nivel-1-Basico/`](Nivel-1-Basico/) | Habilitar eixo e mover | `MC_Power`, `MC_MoveAbsolute`, `MC_MoveRelative`, `MC_Halt`, `MC_Stop` |
| 2 — Intermediário | [`Nivel-2-Intermediario/`](Nivel-2-Intermediario/) | Referenciamento (home) e eixo rotativo | `MC_Home`, `MC_MoveModulo`, `MC_Direction` |
| 3 — Avançado | [`Nivel-3-Avancado/`](Nivel-3-Avancado/) | Erros e sequenciamento automático | `MC_Reset`, máquina de estados (`CASE`), interlocks |
| 4 — Simulado | [`Nivel-4-Simulado-Prova/`](Nivel-4-Simulado-Prova/) | Cenário completo estilo prova de certificação | Todos os anteriores combinados |

## Convenção de eixos usada nos gabaritos

Para reaproveitar o projeto `MotionControl` já existente, os gabaritos assumem:

- `GVL_Axes.Axis1` → **eixo linear (fuso)** — escala em mm/volta, faz *home* sempre ao ligar.
- `GVL_Axes.Axis2` → **eixo rotativo (mesa indexadora)** — escala em graus/volta, **não** faz *home*
  (eixo absoluto/multiturn que preserva posição ao desligar, como um encoder absoluto).

Cada exercício deixa explícito qual escala configurar em cada eixo. Ajuste em
*Solution Explorer → NC → Axes → Axis N → Parameter → Scaling Factor Numerator*.

## Sobre a prova prática

A prova real cobra, em um único cenário, os seguintes pontos (não copie os valores abaixo, eles
mudam a cada exercício de treino para forçar você a entender a lógica, não a decorar):

- Configuração de escala dos eixos (graus/volta e mm/volta).
- Referência (home) diferente por eixo — um eixo homa, o outro não.
- Bloqueio de início de ciclo automático sem eixos habilitados e referenciados.
- Sequência de ciclo automático com indexação de mesa + avanço/recuo de ferramenta em loop contínuo.
- Fim de ciclo suave (termina o ciclo em andamento antes de parar).
- Tratamento de erro global com `MC_Reset` e bloqueio/desbloqueio de novo ciclo.
- Interlocks: botões de referência/reset não podem interferir durante o ciclo automático.

O [Nível 4](Nivel-4-Simulado-Prova/) treina exatamente essa combinação de exigências.
