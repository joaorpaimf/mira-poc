"""
MIRA - Modelo de Inspecao e Resposta Autonoma
POC: verificacao de EPI (capacete + colete) pela webcam.

Uso:
    python mira_webcam.py                 # webcam padrao
    python mira_webcam.py --camera 1      # outra camera
    python mira_webcam.py --fonte video.mp4

Teclas:  Q = sair   |   S = salvar foto do frame atual
"""
import argparse
import csv
import os
import platform
import time
from collections import deque
from datetime import datetime

import cv2
from ultralytics import YOLO

# Classes do modelo treinado
CAPACETE, SEM_CAPACETE, COLETE, SEM_COLETE, PESSOA = 0, 1, 2, 3, 4

# Cores (BGR)
VERDE = (60, 180, 75)
VERMELHO = (40, 40, 220)
AMARELO = (0, 200, 255)
CINZA = (160, 160, 160)
BRANCO = (255, 255, 255)
AZUL_MARINHO = (80, 30, 10)

COR_CLASSE = {
    CAPACETE: VERDE,
    COLETE: VERDE,
    SEM_CAPACETE: VERMELHO,
    SEM_COLETE: VERMELHO,
    PESSOA: CINZA,
}
NOME_TELA = {
    CAPACETE: "capacete",
    COLETE: "colete",
    SEM_CAPACETE: "SEM capacete",
    SEM_COLETE: "SEM colete",
    PESSOA: "pessoa",
}


def centro(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def dentro(ponto, caixa, folga=0.1):
    """Ponto dentro da caixa (com uma folga proporcional ao tamanho da caixa)."""
    x, y = ponto
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    return (caixa[0] - folga * w <= x <= caixa[2] + folga * w and
            caixa[1] - folga * h <= y <= caixa[3] + folga * h)


def avaliar_frame(deteccoes):
    """
    Recebe lista de (classe, conf, caixa) e decide o status do frame.
    Retorna (status, faltando, pessoas)
      status: "OK", "NAO_CONFORME" ou "SEM_PESSOA"
      faltando: set com "capacete"/"colete"
      pessoas: lista de (caixa, ok, faltando) para desenhar
    """
    pessoas = [d for d in deteccoes if d[0] == PESSOA]
    epis = [d for d in deteccoes if d[0] != PESSOA]

    # Na portaria a pessoa costuma ficar muito perto da camera e o
    # modelo pode nao achar a "pessoa" inteira. Nesse caso, avaliamos
    # o frame todo como se fosse uma pessoa so.
    if not pessoas:
        if not epis:
            return "SEM_PESSOA", set(), []
        pessoas = [(PESSOA, 1.0, None)]

    resultado = []
    faltando_geral = set()
    for _, _, caixa in pessoas:
        tem = {c for c, _, b in epis if caixa is None or dentro(centro(b), caixa)}
        faltando = set()
        if CAPACETE not in tem or SEM_CAPACETE in tem:
            faltando.add("capacete")
        if COLETE not in tem or SEM_COLETE in tem:
            faltando.add("colete")
        resultado.append((caixa, not faltando, faltando))
        faltando_geral |= faltando

    status = "OK" if not faltando_geral else "NAO_CONFORME"
    return status, faltando_geral, resultado


def desenhar_caixa(frame, caixa, cor, texto, espessura=2):
    x1, y1, x2, y2 = map(int, caixa)
    cv2.rectangle(frame, (x1, y1), (x2, y2), cor, espessura)
    (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    y_txt = max(y1, th + 8)
    cv2.rectangle(frame, (x1, y_txt - th - 8), (x1 + tw + 8, y_txt), cor, -1)
    cv2.putText(frame, texto, (x1 + 4, y_txt - 5), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, BRANCO, 1, cv2.LINE_AA)


def desenhar_painel(frame, status, faltando, fps):
    h, w = frame.shape[:2]
    if status == "OK":
        cor, texto = VERDE, "LIBERADO"
        detalhe = "Capacete e colete OK"
    elif status == "NAO_CONFORME":
        cor, texto = VERMELHO, "BLOQUEADO"
        detalhe = "Falta: " + ", ".join(sorted(faltando))
    elif status == "VERIFICANDO":
        cor, texto = AMARELO, "VERIFICANDO..."
        detalhe = "Fique parado de frente para a camera"
    else:
        cor, texto = CINZA, "AGUARDANDO"
        detalhe = "Posicione-se em frente a camera"

    # Barra superior com a marca
    cv2.rectangle(frame, (0, 0), (w, 36), AZUL_MARINHO, -1)
    cv2.putText(frame, "MIRA | Verificacao de EPI", (12, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, BRANCO, 2, cv2.LINE_AA)
    cv2.putText(frame, f"{fps:4.1f} FPS", (w - 110, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, BRANCO, 1, cv2.LINE_AA)

    # Barra inferior com o status
    cv2.rectangle(frame, (0, h - 70), (w, h), cor, -1)
    cv2.putText(frame, texto, (16, h - 32), cv2.FONT_HERSHEY_SIMPLEX,
                1.1, BRANCO, 3, cv2.LINE_AA)
    cv2.putText(frame, detalhe, (18, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, BRANCO, 1, cv2.LINE_AA)


class Registro:
    """Salva cada verificacao em CSV + foto quando for nao conforme."""

    def __init__(self, pasta="registros"):
        self.pasta = pasta
        os.makedirs(os.path.join(pasta, "fotos"), exist_ok=True)
        self.csv = os.path.join(pasta, "verificacoes.csv")
        if not os.path.exists(self.csv):
            with open(self.csv, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["data_hora", "status", "faltando", "foto"])

    def salvar(self, status, faltando, frame):
        agora = datetime.now()
        foto = ""
        if status == "NAO_CONFORME":
            foto = os.path.join(self.pasta, "fotos",
                                agora.strftime("%Y%m%d_%H%M%S") + ".jpg")
            cv2.imwrite(foto, frame)
        with open(self.csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([agora.strftime("%Y-%m-%d %H:%M:%S"), status,
                                    "|".join(sorted(faltando)), foto])
        print(f"[{agora:%H:%M:%S}] {status} {', '.join(sorted(faltando))}")


def abrir_fonte(fonte):
    if fonte.isdigit():
        idx = int(fonte)
        # No Windows o backend DirectShow abre a webcam bem mais rapido
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    else:
        cap = cv2.VideoCapture(fonte)
    return cap


def main():
    ap = argparse.ArgumentParser(description="MIRA - POC de verificacao de EPI")
    ap.add_argument("--modelo", default="mira_ppe.pt", help="arquivo do modelo")
    ap.add_argument("--camera", default="0", help="indice da webcam (0, 1, ...)")
    ap.add_argument("--fonte", default=None, help="video ou stream (ex.: RTSP de CFTV)")
    ap.add_argument("--conf", type=float, default=0.35, help="confianca minima")
    ap.add_argument("--imgsz", type=int, default=480,
                    help="tamanho da imagem no modelo (menor = mais rapido)")
    ap.add_argument("--janela", type=int, default=15,
                    help="frames usados para confirmar o status (evita piscar)")
    args = ap.parse_args()

    modelo = YOLO(args.modelo)
    cap = abrir_fonte(args.fonte or args.camera)
    if not cap.isOpened():
        print("Nao consegui abrir a camera/fonte. Tente --camera 1")
        return

    registro = Registro()
    historico = deque(maxlen=args.janela)
    status_confirmado = "SEM_PESSOA"
    faltando_confirmado = set()
    fps, t_ant = 0.0, time.time()

    print("MIRA rodando. Q para sair, S para salvar foto.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        res = modelo.predict(frame, conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
        deteccoes = [(int(c), float(p), b.tolist()) for c, p, b in
                     zip(res.boxes.cls, res.boxes.conf, res.boxes.xyxy)]

        status, faltando, pessoas = avaliar_frame(deteccoes)
        historico.append((status, frozenset(faltando)))

        # So muda o status quando a maioria dos ultimos frames concorda
        votos = [s for s, _ in historico]
        mais_comum = max(set(votos), key=votos.count)
        if votos.count(mais_comum) >= 0.7 * len(historico) and len(historico) == historico.maxlen:
            falt = [f for s, f in historico if s == mais_comum]
            novo_faltando = set(max(set(falt), key=falt.count))
            if mais_comum != status_confirmado or novo_faltando != faltando_confirmado:
                status_confirmado, faltando_confirmado = mais_comum, novo_faltando
                if status_confirmado != "SEM_PESSOA":
                    registro.salvar(status_confirmado, faltando_confirmado, frame)
        painel = status_confirmado
        if status != "SEM_PESSOA" and status_confirmado == "SEM_PESSOA":
            painel = "VERIFICANDO"

        # Desenho
        for c, p, b in deteccoes:
            if c != PESSOA:
                desenhar_caixa(frame, b, COR_CLASSE[c], f"{NOME_TELA[c]} {p:.0%}")
        for caixa, ok_p, falt in pessoas:
            if caixa is not None:
                cor = VERDE if ok_p else VERMELHO
                txt = "OK" if ok_p else "falta: " + ", ".join(sorted(falt))
                desenhar_caixa(frame, caixa, cor, txt, 3)

        agora = time.time()
        fps = 0.9 * fps + 0.1 * (1 / max(agora - t_ant, 1e-6))
        t_ant = agora
        desenhar_painel(frame, painel, faltando_confirmado, fps)

        cv2.imshow("MIRA - Verificacao de EPI", frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("q"):
            break
        if tecla == ord("s"):
            nome = datetime.now().strftime("captura_%Y%m%d_%H%M%S.jpg")
            cv2.imwrite(os.path.join(registro.pasta, nome), frame)
            print("Foto salva:", nome)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
