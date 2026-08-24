# Exercício 07 — Simulado Completo (estilo Prova de Certificação de Motion)

**Nível:** 4 — Simulado

## Cenário

Este exercício combina **tudo** o que foi treinado nos níveis 1 a 3 em um único cenário completo,
com a mesma estrutura conceitual da prova prática de certificação — mas com números diferentes,
para você treinar o raciocínio e não decorar uma resposta pronta.

Uma mesa rotativa transporta produtos até uma estação de trabalho. A cada volta, existem
**8 posições de produto, espaçadas 45° uma da outra** (0-45-90-135-180-225-270-315). Um eixo
linear (fuso) empurra uma ferramenta sobre o produto posicionado na estação.

- `GVL_Axes.Axis2` = motor da mesa rotativa. Escala: **360° por volta**. **Não faz home** — é um
  eixo absoluto que preserva a posição mesmo desligando a máquina.
- `GVL_Axes.Axis1` = motor do fuso (ferramenta). Escala: **5 mm por volta**. **Faz home sempre que
  a máquina liga**, e o sensor de home está na posição "0".

## Mapeamento de E/S (nomenclatura livre — sugestão a seguir a da prova real)

| Sinal | Descrição |
|---|---|
| `xLigarCiclo` | Botão liga o ciclo automático |
| `xPararCiclo` | Botão pede fim de ciclo (efetiva só ao fim do ciclo em andamento) |
| `xBotaoReferencia` | Botão de referência (home) manual |
| `xSensorHomeFuso` | Sensor de home do motor do fuso, na posição "0" |
| `xHabilitaEixos` | Habilita os dois eixos |
| `xBotaoReset` | Botão de reset de falha |
| `xCicloLigado` | Sinalização: ciclo automático ligado |
| `xEixosReferenciados` | Sinalização: ambos os eixos referenciados |
| `xFalhaEixos` | Sinalização: falha em algum dos eixos |

## O que fazer

1. **Configuração dos eixos** — configure as escalas pedidas acima em cada eixo na NC.
2. **Referência**:
   - O motor da mesa **não** deve ter nenhum bloco `MC_Home` chamado — trate-o como já
     referenciado permanentemente (ou seja, considere `xEixosReferenciados` dependente apenas da
     referência do fuso).
   - O motor do fuso deve ser referenciado com `MC_Home` (posição 0 no sensor de home), e essa
     referência é perdida sempre que o eixo é desabilitado.
3. **Interlock de início de ciclo** — o ciclo automático só pode iniciar se:
   - Ambos os eixos estiverem habilitados (`MC_Power.Status = TRUE`), **e**
   - O fuso estiver referenciado (`xEixosReferenciados = TRUE`).
4. **Sequência do ciclo automático** (implemente como máquina de estados `CASE`):
   - **A)** Posiciona a ferramenta (fuso) na posição de repouso **5 mm** (`MC_MoveAbsolute`).
   - **B)** Caso a mesa não esteja exatamente em uma posição de produto (múltiplo de 45°),
     posiciona a mesa para a **primeira posição de produto no sentido positivo**
     (`MC_MoveModulo`, `Direction := MC_Positive_Direction`) — reaproveite a fórmula do
     Exercício 04, mas agora com passo de 45°.
   - **C)** A ferramenta avança até **40 mm**, aguarda **1 segundo**, recua de volta para **5 mm**.
   - **D)** A mesa gira para a próxima posição de produto (sentido positivo, sempre).
   - **E)** Os passos C e D repetem continuamente até o comando de fim de ciclo.
5. **Fim de ciclo suave** — `xPararCiclo` só efetiva a parada depois que o ciclo em andamento
   (avanço + espera + recuo + giro da mesa) terminar por completo.
6. **Tratamento de erro** — qualquer erro em qualquer eixo deve: desligar o ciclo automático,
   desabilitar os dois eixos e manter `xFalhaEixos = TRUE` até reset. `xBotaoReset` só deve ter
   efeito quando há falha real.
7. **Depois de um reset**, deve ser possível habilitar os eixos, referenciar o fuso novamente e
   iniciar um novo ciclo automático — sem reiniciar o programa.
8. **Interlocks finais**:
   - `xBotaoReferencia` e `xSensorHomeFuso` não podem interferir durante o ciclo automático
     (ou seja, o `MC_Home` só pode ser disparado com o ciclo automático **desligado**).
   - `xBotaoReset` não pode interferir durante o ciclo automático (só age quando há falha).

## Elementos da biblioteca Motion exigidos (revisão de tudo)

- `MC_Power`, `Axis.ReadStatus()`, `Axis.Status` — Exercício 01
- `MC_MoveAbsolute`, `MC_Halt`/`MC_Stop` (opcional para parada manual) — Exercício 02
- `MC_Home` — Exercício 03
- `MC_MoveModulo` + `MC_Direction.MC_Positive_Direction` — Exercício 04
- `MC_Reset` + lógica de falha global — Exercício 05
- Máquina de estados `CASE` para ciclo contínuo com parada suave — Exercício 06

## Critérios de aceite (auto-avaliação, espelhando os pesos da prova real)

- [ ] Escalas dos dois eixos configuradas corretamente.
- [ ] Motor da mesa não tem `MC_Home` e preserva posição ao desligar.
- [ ] Motor do fuso referencia corretamente na posição do sensor de home.
- [ ] Ciclo não inicia sem eixos habilitados e fuso referenciado.
- [ ] Sequência A→B→C→D→E implementada corretamente, incluindo indexação sempre positiva.
- [ ] Fim de ciclo espera o ciclo atual terminar antes de parar.
- [ ] Qualquer erro para tudo, desabilita eixos e sinaliza falha.
- [ ] Reset só funciona havendo falha, e libera novo ciclo depois.
- [ ] Botão de referência e sensor de home não interferem durante o ciclo automático.
- [ ] Botão de reset não interfere durante o ciclo automático (sem falha).

Compare sua solução com o `Gabarito.TcPOU` + `E_EstadoCicloAutomatico.TcDUT` desta pasta somente
depois de tentar resolver sozinho.
