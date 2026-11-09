# Exercício 08: Came eletrônico (camming)

**Nível:** 5 (Camming)

## Cenário

No Ex07 o fuso avançava, esperava 1 s com um `TON` e recuava, tudo comandado por uma máquina de
estados. Aqui o mesmo curso é feito por um **came eletrônico**: o fuso (escravo) segue uma tabela de
posição em função de um **eixo mestre virtual**. O tempo de cada trecho passa a depender só da
velocidade do mestre, não de temporizadores.

## Eixos e escalas

- **`GVL_Axes.Axis3`** (mestre virtual): rotativo, 360° por volta, **módulo de 360°**, simulado.
  Gira em velocidade constante.
- **`GVL_Axes.Axis1`** (fuso, escravo): igual ao Ex07, 5 mm por volta, faz home a cada partida.
- `GVL_Axes.Axis2` (mesa do Ex07) não é usado neste exercício.

## Perfil do came (uma volta do mestre)

| Mestre (graus) | Escravo (mm) | Trecho |
|---|---|---|
| 0 a 120 | 5 → 40 | avança, perfil cicloidal |
| 120 a 180 | 40 | espera |
| 180 a 300 | 40 → 5 | recua, perfil cicloidal |
| 300 a 360 | 5 | espera (zona de repouso) |

Cicloidal: `S(s) = s - sin(2·π·s) / (2·π)`, com `s` de 0 a 1 em cada trecho. Começa e termina com
velocidade e aceleração zero. Pontos de conferência: mestre 60° → **22,5 mm**; 120° a 180° →
**40 mm**; 240° → **22,5 mm**; 300° a 360° → **5 mm**.

## Mapeamento de E/S

| Sinal | Função |
|---|---|
| `xHabilitaEixos` | Habilita fuso e mestre |
| `xBotaoReferencia` | Home manual do fuso (só com o came desligado) |
| `xLigarCame` | Liga o ciclo do came |
| `xPararCame` | Pede o fim do ciclo (efetiva só na zona de repouso) |
| `xBotaoReset` | Reset de falha |
| `xCameLigado` | Ciclo ligado |
| `xSincronizado` | Fuso acoplado e seguindo a tabela |
| `xFalhaEixos` | Falha em algum eixo |

## Tarefas

1. **Eixos:** configurar o mestre (`Axis3`, 360°/volta, módulo, simulado) e manter o fuso como no Ex07.
2. **Tabela por código:** montar em um array `ARRAY [0..360, 0..1] OF LREAL` os 361 pontos do perfil
   (coluna 0 = mestre em graus, coluna 1 = escravo em mm), com uma função de perfil sua.
3. **Carregar no NC:** descrever o array em um `MC_CAM_REF` (`pArray`, `ArraySize`, `TableType`,
   `NoOfRows`, `NoOfColumns`) e usar `MC_CamTableSelect` com `Periodic := TRUE`.
4. **Interlock de início:** o ciclo só inicia com os dois eixos habilitados, o fuso referenciado e
   sem falha.
5. **Pré-posicionar:** antes de acoplar, levar o fuso a 5 mm e o mestre a 0°.
6. **Acoplar:** `MC_CamIn` em modo absoluto; só depois de `InSync` o mestre começa a girar a 60°/s
   (`MC_MoveVelocity`, sentido positivo).
7. **Fim de ciclo suave:** `xPararCame` só desacopla quando o mestre estiver entre 300° e 360°
   (fuso parado em repouso): `MC_CamOut` e, em seguida, `MC_Halt` no mestre.
8. **Falha:** erro em qualquer eixo desliga o ciclo, desabilita os dois eixos e mantém
   `xFalhaEixos` até o reset, como no Ex07.
9. **Verificar no Scope** (ver a nota *Motion Axis Scope* do vault): posição do fuso contra posição
   do mestre, e conferir os pontos de referência da tabela acima.

## Blocos Motion exigidos

- `MC_Power`, `MC_Home`, `MC_Reset` (Ex01, Ex03, Ex05)
- `MC_MoveAbsolute`, `MC_MoveModulo`, `MC_Halt` (Ex02, Ex04)
- `MC_MoveVelocity` (mestre em velocidade constante)
- `MC_CamTableSelect`, `MC_CamIn`, `MC_CamOut` (novos)

## Critérios de aceite

- A tabela tem 361 pontos, fecha (escravo em 0° igual ao escravo em 360°) e passa pelos pontos de
  conferência.
- O fuso só acopla com o mestre em 0° e o fuso em 5 mm; o mestre só gira depois do `InSync`.
- O ciclo não inicia sem os eixos habilitados e o fuso referenciado.
- O fuso nunca sai da faixa de 5 a 40 mm, e fica parado nas duas esperas.
- Parada só na zona de repouso, com o fuso em 5 mm.
- Qualquer erro para tudo, desabilita os eixos e sinaliza falha; o reset só age com falha.
- Referência e reset não interferem durante o ciclo.

## Preparando o projeto

Não há `.tsproj` aqui (eles são gerados pelo XAE). Para montar:

1. Copie `Nivel-4-Simulado-Prova/Ex07-SimuladoCertificacao/TwinCAT Project1` para uma pasta nova.
2. Em *NC → Axes*, adicione um terceiro eixo simulado (mesmo procedimento de `Axis1` e `Axis2`),
   com escala 360° por volta e **módulo** de 360° (ver o Ex04). Declare `Axis3 : AXIS_REF;` em `GVL_Axes`.
3. Adicione a biblioteca **`Tc2_MC2_Camming`** (versão 3.4.0 ou superior) em *References*.
4. Licença **TF5050 (TwinCAT 3 NC Camming)**, em modo trial de 7 dias se preferir, em *SYSTEM → License*.
5. Importe `E_EstadoCame.TcDUT`, `F_PerfilCame.TcPOU` e `Gabarito.TcPOU` (ou crie os seus) e chame o
   programa a partir do `MAIN`.

## Ferramenta de conferência (Python)

`tools/gen_cam_table.py` calcula o mesmo perfil, valida a tabela e informa velocidade e aceleração
de pico do fuso para uma velocidade do mestre:

```bash
python tools/gen_cam_table.py --csv perfil_came.csv --plot perfil_came.png
python tools/gen_cam_table.py --omega 90
```

Com o mestre a 60°/s: período de 6 s, velocidade de pico de 35 mm/s e aceleração de pico de
cerca de 55 mm/s² no fuso. Os testes (`python -m pytest tools`) cobrem o perfil, a periodicidade e a
zona de repouso. `perfil_came.csv` e `perfil_came.png` são a saída padrão.

## Experimentos (anote o que observar)

- Mestre a 30°/s e a 120°/s: como mudam o período e a aceleração do fuso? Compare com a saída da
  ferramenta.
- Trocar o perfil cicloidal por linear (`S = s`) e olhar a velocidade no Scope.
- Acionar `xPararCame` fora da zona de repouso e confirmar que o ciclo só termina ao entrar nela.
- Provocar um erro no fuso durante o acoplamento e conferir se, após o reset, o fuso ainda está
  acoplado (ver a observação no gabarito).

## Dicas

Os arquivos `Gabarito.TcPOU`, `F_PerfilCame.TcPOU` e `E_EstadoCame.TcDUT` só devem ser consultados
depois de tentar sozinho. **O gabarito ainda não foi compilado nem testado no XAE**: confira os nomes
dos identificadores (por exemplo `MC_STARTMODE_ABSOLUTE`, `MC_TABLETYPE_EQUIDISTANT`) no Library
Manager da sua versão.

## Referências

- [Infosys - MC_CamTableSelect](https://infosys.beckhoff.com/content/1033/tcplclibmc2_camming/460400651.html)
- [Infosys - MC_CamIn](https://infosys.beckhoff.com/content/1033/tcplclibmc2_camming/460403723.html)
- [Infosys - MC_CamOut](https://infosys.beckhoff.com/content/1033/tf5050_tc3_nc_camming/1002381451.html)
- [Infosys - MC_CAM_REF](https://infosys.beckhoff.com/content/1033/tcplclibmc2_camming/460439563.html)
- [Infosys - visão geral da biblioteca de camming (TF5050)](https://infosys.beckhoff.com/content/1033/tf5050_tc3_nc_camming/6961172235.html)
