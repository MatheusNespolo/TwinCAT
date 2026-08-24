# Exercício 04 — Eixo Rotativo com Indexação Angular (Modulo)

**Nível:** 2 — Intermediário

## Cenário

Uma mesa rotativa gira continuamente em torno de si mesma (0° a 360°, "dá a volta" e recomeça em
0°). Diferente do eixo linear, este eixo:

- **Não faz home** — ele é tratado como um eixo absoluto (tipo encoder absoluto/multiturn) que
  mantém a posição real mesmo depois de desligar e religar a máquina.
- Precisa se mover sempre **em sentido positivo**, indexando de posição em posição.

Neste exercício a mesa tem produtos posicionados a cada **45°** (8 posições: 0-45-90-135-180-225-
270-315), diferente da prova real (que usa 30°) — o objetivo é praticar a lógica de "achar a
próxima posição válida", não decorar um valor fixo.

## O que fazer

Usando `GVL_Axes.Axis2` (eixo rotativo, escala graus/volta):

1. Configure a escala do `Axis2` para 360°/volta.
2. Marque `Axis2` como eixo modulo em *NC → Axes → Axis 2 → Parameter → Modulo* com
   comprimento `360.0` (isso faz o eixo "dar a volta" automaticamente).
3. Crie uma função/lógica que, dada a posição atual do eixo (`Axis2.NcToPlc.ActPos`), calcule qual
   é a **próxima posição múltipla de 45° no sentido positivo** (ex.: se a posição atual for 100°,
   a próxima posição de produto é 135°).
4. Use `MC_MoveModulo` com `Direction := MC_Direction.MC_Positive_Direction` para sempre girar a
   mesa no sentido positivo até a próxima posição calculada.
5. Disparo do movimento: `xIndexarMesa : BOOL` (borda de subida).

## Elementos da biblioteca Motion exigidos

- `MC_MoveModulo` (movimento em eixo modulo/circular)
- `MC_Direction` (enum: `MC_Positive_Direction`, `MC_Negative_Direction`, `MC_Shortest_Way`, `MC_Current_Direction`)
- `Axis.NcToPlc.ActPos` (posição atual do eixo, para calcular a próxima posição válida)

## Critérios de aceite

- A mesa nunca deve girar no sentido negativo para "economizar caminho" — sempre positivo, mesmo
  que o `MC_Shortest_Way` fosse mais curto.
- O cálculo da próxima posição deve funcionar mesmo quando a posição atual já é exatamente uma
  posição de produto (ex.: se está em 90°, a próxima deve ser 135°, não 90°).
- Deve funcionar corretamente na "virada" de 360° para 0° (ex.: se está em 340°, a próxima posição
  positiva é 0°/360°, dependendo de como seu eixo modulo trata o wrap).

## Dica de fórmula

Uma forma comum de calcular "próximo múltiplo de N no sentido positivo, estritamente maior que a
posição atual" é:

```
lrProximaPosicao := (TRUNC(ActPos / 45.0) + 1) * 45.0;
```

Cuidado com o caso em que `ActPos` já é múltiplo exato de 45 — o `TRUNC` sozinho já resolve isso
corretamente, pois sempre soma 1.
