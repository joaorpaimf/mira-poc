# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

MIRA (Modelo de Inspeção e Resposta Autônoma) é uma POC que verifica EPI (capacete + colete) pela webcam e mostra LIBERADO/BLOQUEADO. Código, comentários, nomes de variáveis e textos da interface estão em português — manter assim. Os comentários do `mira_webcam.py` são escritos sem acento (ASCII); o README e o notebook usam acentos.

## Comandos

Ambiente Windows, Git Bash (`source venv/Scripts/activate`):

```
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
python mira_webcam.py                      # webcam 0
python mira_webcam.py --camera 1           # outra webcam
python mira_webcam.py --fonte video.mp4    # arquivo ou rtsp://... (CFTV)
python mira_webcam.py --conf 0.5 --imgsz 480 --janela 45 --modelo mira_ppe.pt
```

Na janela do vídeo: `Q` sai, `S` salva foto em `registros/`, `F` alterna tela cheia (abre em tela cheia). Não há testes, lint nem build. `--fonte video.mp4` é a forma de testar sem câmera.

## Arquitetura

Duas partes ligadas pelo arquivo de pesos `mira_ppe.pt` (versionado no repo):

1. **Treino** — `MIRA_treino_colab.ipynb`, roda no Google Colab (GPU T4). Baixa o dataset Construction Site Safety (Roboflow, CC BY 4.0), remapeia os ids originais para 5 classes (`MAPA = {0: 0, 2: 1, 7: 2, 4: 3, 5: 4}`), treina YOLO26n (Ultralytics, 50 épocas, 640px) e baixa o `best.pt` como `mira_ppe.pt`.

2. **Execução** — `mira_webcam.py`, script único:
   - `abrir_fonte()`: OpenCV; no Windows usa `CAP_DSHOW` para webcam (abre mais rápido), 848x480 (16:9, preenche a tela cheia) a 30 FPS. Não voltar para 1280x720: no DirectShow essa resolução só sai em YUY2 a 10 FPS (MJPG é ignorado).
   - `carregar_modelo()`: se `--modelo` é `.pt`, exporta uma vez para `<nome>_openvino_model/` (fora do git) e usa essa pasta; reexporta se o `imgsz` do `metadata.yaml` for diferente de `--imgsz`. No CPU o OpenVINO faz a inferência em ~20 ms, contra ~95 ms do PyTorch. `aquecer()` roda a 1ª inferência (que compila o modelo e leva ~10 s) antes de abrir a câmera.
   - Webcam/RTSP: `InferenciaEmThread` roda o `Verificador` numa thread, sempre no frame mais recente. O loop principal lê, desenha o último resultado e exibe na velocidade da câmera. Arquivo de vídeo (`os.path.isfile`) roda sequencial, frame a frame. O painel mostra `FPS | IA`.
   - `Verificador.processar()`: `modelo.predict()` → lista de `(classe, conf, caixa_xyxy)`, depois avaliação e estabilização abaixo.
   - `avaliar_frame()`: associa cada EPI à pessoa cujo box contém o centro do EPI (com folga de 10%, `dentro()`). Se nenhuma `pessoa` for detectada mas houver EPIs, trata o frame inteiro como uma pessoa (caso de pessoa muito perto da câmera na portaria). Retorna `OK`, `NAO_CONFORME` ou `SEM_PESSOA`.
   - Estabilização: `deque` com os últimos `--janela` frames; o status confirmado só muda quando o histórico está cheio e ≥70% dos frames concordam. A janela conta frames *inferidos*; o padrão 45 ≈ 1,5 s a 30 FPS. O painel mostra `VERIFICANDO` enquanto há detecção mas nada confirmado.
   - `Registro`: a cada mudança de status confirmado (exceto `SEM_PESSOA`) grava linha em `registros/verificacoes.csv` e, se `NAO_CONFORME`, salva foto em `registros/fotos/`.

### Contrato de classes

Os ids das classes são fixos e compartilhados entre o notebook (`NOMES`) e o script (`CAPACETE, SEM_CAPACETE, COLETE, SEM_COLETE, PESSOA = 0..4`). Mudar classes no treino exige atualizar as constantes, `COR_CLASSE` e `NOME_TELA` em `mira_webcam.py`.

Um EPI conta como faltando se a classe positiva não aparecer **ou** se a negativa (`sem_capacete`/`sem_colete`) aparecer dentro da pessoa.

## Observações

- `registros/` e `venv/` estão no `.gitignore`.
- `docs/arquitetura.excalidraw` é o diagrama de arquitetura (fonte editável, abrir em excalidraw.com); `docs/arquitetura.png` é o export exibido no README — reexportar ao alterar o diagrama.
- Limitações conhecidas: modelo treinado com fotos de obra tiradas de longe, erra mais de perto; YOLO26/Ultralytics é AGPL-3.0 (uso comercial exige licença).

# Development Workflow (mandatory)

Any task that changes behavior follows the phases below, in order. Never merge
phases. Never start Fase 2 without my explicit approval of Fase 1. Never assume
approval on my behalf.

The approval string is literal. Only this advances to Fase 2:
- `Fase 1 aprovada`
Anything else from me ("ok", "pode ir", "isso") is NOT approval.

## Fase 1 — Plan
Output the change plan using the Review Output Format. No implementation code.
Write the plan to `.claude/plans/<slug>.md` (create the folder if it does not exist).
STOP and wait for `Fase 1 aprovada`.

## Fase 2 — Implementation
- Write the code described in the approved plan, with the smallest correct change.
- Do not add files, routes, fields, props or behavior that the approved plan does not cover.
- If the plan turns out to be wrong or incomplete during implementation, STOP and
  report it in the Review Output Format before continuing.

## Fase 3 — Report
Using the Review Output Format, list only: what you left out of the approved plan,
any bug found during implementation, and risks or gaps that matter.
Do not suggest new ideas or improvements outside the plan's scope, and make it
clear that nothing beyond the plan was done.

# Review Output Format
Applies to Fases 1 and 3 and to any code review.
Does NOT apply to implementation files, which are written in full.

1. **Only List Necessary Changes**: no compliments, no positive reinforcement, no
   summary of what went well. Only what must change.
2. **Strict Output Format**: for every finding:
   - **What to change:** [file path and line number] - short description of the fix.
   - **Why to change:** technical justification (bug, performance, security,
     maintainability).
3. **Keep it concise**: no long code blocks or full refactorings unless strictly
   necessary to explain the "Why"
4. **What all this shit means**: after all findings, end with a section titled
   `## What all this shit means` that explains every "What to change" and "Why to
   change" above in plain, non-technical language, as if talking to someone
   who does not program. Rule 3 does not apply to this section: it may be
   longer, use analogies and describe the practical effect for whoever uses
   the MIRA (e.g. the gate operator). No jargon, file names or line numbers.