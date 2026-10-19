# Garment Deform Inspector (Blender)

Ferramenta para analisar **por que uma roupa deforma mal** comparando-a com uma roupa que
deforma bem, no mesmo rig. Foi feita para o caso clássico de VTuber: um moletom oversized
que forma uma "membrana" entre o braço e o tronco ao levantar os braços.

A ferramenta só lê o arquivo. Ela **não modifica** malhas, pesos, Shape Keys, modificadores
nem o rig, e **sempre restaura** a pose, a animação e a visibilidade dos modificadores (inclusive
em caso de erro). Ao final, verifica que a restauração deu certo.

## O que ela faz

| Fase | Conteúdo |
|---|---|
| 1–2. Inspeção | Topologia (tris/quads/n-gons, densidade, vértices sobrepostos, bordas), transformação e parent, pilha de modificadores e opções do Armature (DQS, envelopes, multi-modifier, máscara), vertex groups (sem osso, não deformantes, sem peso, não normalizados, >4 influências), Shape Keys (relativa, valor, vértices movidos, drivers e quais ossos as acionam = corretivas), drivers e constraints do objeto e dos ossos do braço. |
| Zonas de peso | Onde fica a transição tronco→braço em relação ao **pivô do ombro**, o quanto desce pela lateral do tronco, o quanto é abrupta (Δpeso/cm), quantos anéis de aresta a atravessam e a distância entre o tecido com peso de braço e o osso (efeito oversized). |
| Corpo (opcional) | Afastamento roupa↔corpo, vértices dentro do corpo e **comparação com os pesos do corpo** no ponto mais próximo. Pesos idênticos aos do corpo em tecido solto denunciam uma transferência por proximidade. |
| 3. Poses | Braços abaixados, a 45°, na horizontal, acima da cabeça e flexionados diante do corpo. As poses são calculadas a partir do repouso (funcionam em T-pose e A-pose). Para cada uma: estiramento/compressão por triângulo, triângulos-ponte (salto de peso > 0.5), tronco longe do braço e interpenetração com o corpo. |
| 4–5. Diagnóstico | Regras que separam **CONFIRMADO / DESCARTADO / HIPÓTESE / OBSERVAÇÃO** com a evidência numérica, e um plano de correção priorizado com riscos. Inclui o teste "o esqueleto é a causa?": mesmo rig + original boa + nova ruim ⇒ descartado. |

Saída: `relatorio.md` (seções A–G), `dados.json` com todos os números e imagens SVG lado a lado
(peso de braço e estiramento por pose, na mesma escala), geradas direto da malha, sem render.

## Instalação

**Blender 4.2+:** compacte a pasta `garment_deform_inspector` em `.zip` e use
*Edit ▸ Preferences ▸ Get Extensions ▸ ⌄ ▸ Install from Disk* (ou *Add-ons ▸ Install* em versões antigas).

Painel: *View3D ▸ barra lateral (N) ▸ aba **Roupa 3D***.

1. Escolha **Roupa original**, **Roupa nova**, **Corpo** (opcional, mas recomendado) e **Armature**.
2. **Detectar ossos** e confira Shoulder/UpperArm/LowerArm de cada lado (VRM, VRoid, Mixamo, MMD,
   Rigify e nomes do VRChat são reconhecidos; dá para escolher manualmente).
3. Confira **Frente do personagem** (−Y é o padrão do Blender/VRM).
4. **Analisar e gerar relatório**.
5. Opcional: **Criar cópias diagnósticas** gera duplicatas na coleção `GDI_Diagnostico` com
   atributos de cor (`GDI_peso_braco`, `GDI_estir_<POSE>`, `GDI_dif_corpo`). Elas acompanham o rig,
   então dá para posar e ver ao vivo. Para visualizar: *Viewport Shading ▸ Color ▸ Attribute*.
   Os originais não são tocados.
6. **Pré-visualizar pose / Restaurar pose** para olhar uma pose de teste e voltar exatamente ao estado anterior.

## Linha de comando (o arquivo é aberto e nunca salvo)

```bash
blender -b personagem.blend --python blender/cli_inspect.py -- --list
blender -b personagem.blend --python blender/cli_inspect.py -- \
    --original "Jaqueta" --new "Moletom" --body "Body" --armature "Armature" --out ./relatorio
# sobrescrever ossos: --bone L.upper_arm=J_Bip_L_UpperArm --bone R.upper_arm=J_Bip_R_UpperArm
```

## Como ler as métricas

- **Estiramento** = maior razão de comprimento de cada triângulo em relação à pose abaixada
  (1.0 = igual; 2.0 = dobrou). Segmentos de referência menores que 1 mm são ignorados. A coluna
  "vs repouso" compara com a malha como foi modelada.
- **Axila** = até 1 comprimento de UpperArm do ombro e abaixo dele.
- **Compressão p5 < 0.5** = tecido se sobrepondo, o que gera volume artificial e dobras.
- **Fronteira longe do pivô**: a rotação do braço afasta pontos proporcionalmente à distância até
  a articulação. Uma fronteira de peso abrupta na lateral do tronco abre muito mais do que uma
  junto ao ombro. Essa é a causa geométrica típica da membrana em roupas drop-shoulder/oversized.

## Limitações

- É uma análise de skinning, não simulação de tecido.
- Drivers, constraints, Corrective Smooth e Dual Quaternion **não** vão para VRM/Unity. O relatório
  lembra disso ao recomendar correções.
- Modificadores que mudam a topologia (Subdivision, Solidify…) ficam desligados só durante a
  medição, para manter a correspondência 1:1 de vértices, e são religados depois.
- As configurações do painel ficam guardadas na cena (`scene.gdi`) e vão junto se você salvar o arquivo.

## Testes

```bash
python -m venv venv && venv/bin/pip install bpy
venv/bin/python blender/tests/synthetic_scene.py /tmp/gdi   # rig + corpo + roupa boa + moletom com defeitos
venv/bin/python blender/tests/test_bone_names.py
```

A cena sintética injeta defeitos conhecidos (peso de braço descendo pelo tronco, fronteira
abrupta, vértices sem peso, DQS diferente) e confere que todos são detectados e que a pose e os
modificadores voltam ao estado original.
