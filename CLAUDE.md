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
python mira_webcam.py --conf 0.5 --imgsz 480 --janela 15 --modelo mira_ppe.pt
```

Na janela do vídeo: `Q` sai, `S` salva foto em `registros/`. Não há testes, lint nem build. `--fonte video.mp4` é a forma de testar sem câmera.

## Arquitetura

Duas partes ligadas pelo arquivo de pesos `mira_ppe.pt` (versionado no repo):

1. **Treino** — `MIRA_treino_colab.ipynb`, roda no Google Colab (GPU T4). Baixa o dataset Construction Site Safety (Roboflow, CC BY 4.0), remapeia os ids originais para 5 classes (`MAPA = {0: 0, 2: 1, 7: 2, 4: 3, 5: 4}`), treina YOLO26n (Ultralytics, 50 épocas, 640px) e baixa o `best.pt` como `mira_ppe.pt`.

2. **Execução** — `mira_webcam.py`, script único, loop por frame:
   - `abrir_fonte()`: OpenCV; no Windows usa `CAP_DSHOW` para webcam (abre mais rápido), 1280x720.
   - `modelo.predict()` → lista de `(classe, conf, caixa_xyxy)`.
   - `avaliar_frame()`: associa cada EPI à pessoa cujo box contém o centro do EPI (com folga de 10%, `dentro()`). Se nenhuma `pessoa` for detectada mas houver EPIs, trata o frame inteiro como uma pessoa (caso de pessoa muito perto da câmera na portaria). Retorna `OK`, `NAO_CONFORME` ou `SEM_PESSOA`.
   - Estabilização: `deque` com os últimos `--janela` frames; o status confirmado só muda quando o histórico está cheio e ≥70% dos frames concordam. O painel mostra `VERIFICANDO` enquanto há detecção mas nada confirmado.
   - `Registro`: a cada mudança de status confirmado (exceto `SEM_PESSOA`) grava linha em `registros/verificacoes.csv` e, se `NAO_CONFORME`, salva foto em `registros/fotos/`.

### Contrato de classes

Os ids das classes são fixos e compartilhados entre o notebook (`NOMES`) e o script (`CAPACETE, SEM_CAPACETE, COLETE, SEM_COLETE, PESSOA = 0..4`). Mudar classes no treino exige atualizar as constantes, `COR_CLASSE` e `NOME_TELA` em `mira_webcam.py`.

Um EPI conta como faltando se a classe positiva não aparecer **ou** se a negativa (`sem_capacete`/`sem_colete`) aparecer dentro da pessoa.

## Observações

- `registros/` e `venv/` estão no `.gitignore`.
- `docs/arquitetura.excalidraw` é o diagrama de arquitetura (fonte editável, abrir em excalidraw.com); `docs/arquitetura.png` é o export exibido no README — reexportar ao alterar o diagrama.
- Limitações conhecidas: modelo treinado com fotos de obra tiradas de longe, erra mais de perto; YOLO26/Ultralytics é AGPL-3.0 (uso comercial exige licença).
