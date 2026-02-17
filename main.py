import sys
import os
import qrcode
import cv2
import datetime
from pyzbar.pyzbar import decode, ZBarSymbol
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QComboBox, 
                             QFileDialog, QMessageBox, QInputDialog, QListWidget, QListWidgetItem, QCheckBox, QSpinBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor
from database import Database

# Imports pour le PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# --- LOGIQUE DE GESTION DES FICHIERS ---
class LogicManager:
    @staticmethod
    def setup_folders():
        for path in ["data/qrcodes", "data/factures"]:
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def generate_qr(item_id, sn):
        path = f"data/qrcodes/QR_{item_id}.png"
        img = qrcode.make(f"PROSTOCK-ID:{item_id}-SN:{sn}")
        img.save(path)
        return path

# --- DIALOGUES ---
class AddRepairDialog(QDialog):
    def __init__(self, item_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Maintenance : {item_name}")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.date = QLineEdit(); self.date.setText(datetime.date.today().strftime("%Y-%m-%d"))
        self.desc = QLineEdit(); self.cout = QLineEdit(); self.prestataire = QLineEdit()
        form.addRow("Date :", self.date); form.addRow("Description :", self.desc)
        form.addRow("Coût (€) :", self.cout); form.addRow("Réparateur :", self.prestataire)
        layout.addLayout(form); self.btn_save = QPushButton("Enregistrer"); self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.accept); layout.addWidget(self.btn_save)

class SelectItemsDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner les objets")
        self.setFixedSize(400, 500); layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for item_id, nom, marque in items:
            list_item = QListWidgetItem(f"[{item_id}] {marque} - {nom}")
            list_item.setData(Qt.ItemDataRole.UserRole, item_id)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked); self.list_widget.addItem(list_item)
        layout.addWidget(self.list_widget); self.btn_confirm = QPushButton("Valider"); self.btn_confirm.setObjectName("ActionBtn")
        self.btn_confirm.clicked.connect(self.accept); layout.addWidget(self.btn_confirm)
    def get_selected_ids(self):
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count()) if self.list_widget.item(i).checkState() == Qt.CheckState.Checked]

class AddDeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Ajouter Matériel"); self.setFixedWidth(500)
        self.facture_path = ""
        layout = QVBoxLayout(self); self.form = QFormLayout()
        
        self.cat = QComboBox(); self.cat.addItems(["Photo", "Vidéo", "Son", "Câblage", "Accessoires"])
        self.cat.currentTextChanged.connect(self.toggle_cable_fields)
        
        self.nom = QLineEdit(); self.marque = QLineEdit(); self.sn = QLineEdit(); self.prix = QLineEdit()
        self.is_batch = QCheckBox("Gérer en quantité"); self.quantite = QSpinBox()
        self.quantite.setRange(1, 999); self.quantite.setEnabled(False)
        self.is_batch.toggled.connect(lambda c: self.quantite.setEnabled(c)); self.is_batch.toggled.connect(lambda c: self.sn.setEnabled(not c))

        # Champs Câblage
        self.cable_widget = QWidget(); self.cable_layout = QFormLayout(self.cable_widget)
        self.prise_a = QComboBox(); self.prise_a.addItems(["XLR M", "XLR F", "Jack 6.35", "RCA", "USB-C", "HDMI", "Speakon"]); self.prise_a.setEditable(True)
        self.prise_b = QComboBox(); self.prise_b.addItems(["XLR F", "XLR M", "Jack 6.35", "RCA", "USB-C", "HDMI", "Speakon"]); self.prise_b.setEditable(True)
        self.longueur = QLineEdit(); self.longueur.setPlaceholderText("ex: 5m")
        self.cable_layout.addRow("Prise A :", self.prise_a); self.cable_layout.addRow("Prise B :", self.prise_b); self.cable_layout.addRow("Longueur :", self.longueur); self.cable_widget.hide()

        self.form.addRow("Catégorie :", self.cat); self.form.addRow(self.cable_widget)
        self.form.addRow("Nom :", self.nom); self.form.addRow("Marque :", self.marque)
        self.form.addRow("Lot ?", self.is_batch); form_qty = self.form.addRow("Qté :", self.quantite)
        self.form.addRow("S/N :", self.sn); self.form.addRow("Prix :", self.prix)
        self.btn_file = QPushButton("📁 Facture"); self.btn_file.clicked.connect(self.select_file); self.form.addRow(self.btn_file)
        layout.addLayout(self.form); self.btn_save = QPushButton("Enregistrer"); self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.accept); layout.addWidget(self.btn_save)

    def toggle_cable_fields(self, text):
        is_cable = (text == "Câblage")
        self.cable_widget.setVisible(is_cable)
        if is_cable: self.is_batch.setChecked(True); self.marque.setText("Générique")

    def select_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Facture", "", "Images/PDF (*.jpg *.png *.pdf)")
        if f: self.facture_path = f; self.btn_file.setText("✅ OK")

# --- FENÊTRE PRINCIPALE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Studio Inventory Manager v1.0"); self.resize(1200, 800)
        self.db = Database(); self.update_db_schema(); self.load_stylesheet(); self.barcode_buffer = ""

        main_widget = QWidget(); self.setCentralWidget(main_widget); self.main_layout = QHBoxLayout(main_widget)
        self.main_layout.setContentsMargins(0,0,0,0); self.main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QWidget(); self.sidebar.setObjectName("Sidebar"); sidebar_layout = QVBoxLayout(self.sidebar)
        logo = QLabel("PRO-STOCK"); logo.setObjectName("TitleLabel"); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); sidebar_layout.addWidget(logo)
        self.btn_inv = QPushButton("📦 Inventaire"); self.btn_kits = QPushButton("🧰 Kits")
        self.btn_check = QPushButton("🔄 Check In/Out"); self.btn_maint = QPushButton("🛠 Maintenance")
        for b in [self.btn_inv, self.btn_kits, self.btn_check, self.btn_maint]: sidebar_layout.addWidget(b)
        sidebar_layout.addStretch(); self.btn_settings = QPushButton("⚙ Paramètres"); sidebar_layout.addWidget(self.btn_settings)

        # Toast
        self.toast = QLabel(self); self.toast.setObjectName("Toast"); self.toast.hide()
        self.toast_timer = QTimer(); self.toast_timer.timeout.connect(self.toast.hide)

        # Content
        self.content_area = QStackedWidget(); self.content_area.setObjectName("MainContent")
        self.page_inv = self.create_inventory_page(); self.page_kits = self.create_kits_page()
        self.page_check = self.create_check_page(); self.page_maint = self.create_maintenance_page()
        for p in [self.page_inv, self.page_kits, self.page_check, self.page_maint]: self.content_area.addWidget(p)
        self.main_layout.addWidget(self.sidebar); self.main_layout.addWidget(self.content_area)

        self.btn_inv.clicked.connect(lambda: self.content_area.setCurrentIndex(0))
        self.btn_kits.clicked.connect(lambda: self.content_area.setCurrentIndex(1))
        self.btn_check.clicked.connect(lambda: self.content_area.setCurrentIndex(2))
        self.btn_maint.clicked.connect(lambda: self.content_area.setCurrentIndex(3))

        self.load_data(); self.load_kits_data(); self.load_maintenance_data(); self.load_check_data()

    def show_toast(self, message):
        self.toast.setText(message); self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2, self.height() - 80)
        self.toast.show(); self.toast_timer.start(2000)

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if self.barcode_buffer: self.process_scanned_data(self.barcode_buffer); self.barcode_buffer = ""
        else: self.barcode_buffer += event.text()

    def process_scanned_data(self, data):
        try:
            sc_id = data.split("ID:")[1].split("-")[0]; self.toggle_item_status(sc_id)
        except: pass

    def update_db_schema(self):
        cursor = self.db.conn.cursor()
        cols = ["quantite INTEGER DEFAULT 1", "is_lot INTEGER DEFAULT 0", "parent_id INTEGER DEFAULT NULL", "date_sortie TEXT"]
        for c in cols:
            try: cursor.execute(f"ALTER TABLE equipement ADD COLUMN {c}")
            except: pass
        self.db.conn.commit()

    def load_stylesheet(self):
        if os.path.exists("styles.qss"):
            with open("styles.qss", "r") as f: self.setStyleSheet(f.read())

    def create_inventory_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(30,30,30,30)
        header = QHBoxLayout(); title = QLabel("Inventaire"); title.setObjectName("TitleLabel")
        self.search = QLineEdit(); self.search.setPlaceholderText("Rechercher..."); self.search.textChanged.connect(self.load_data)
        btn_p = QPushButton("🖨️"); btn_p.clicked.connect(self.export_qr_sheet)
        btn_m = QPushButton("🛠️"); btn_m.clicked.connect(self.open_repair_dialog)
        btn_a = QPushButton("+ Ajouter"); btn_a.setObjectName("ActionBtn"); btn_a.clicked.connect(self.open_add_dialog)
        header.addWidget(title); header.addWidget(self.search); header.addStretch(); header.addWidget(btn_m); header.addWidget(btn_p); header.addWidget(btn_a)
        layout.addLayout(header); self.table = QTableWidget(); self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Marque", "S/N", "Qté", "Statut", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(45); layout.addWidget(self.table); return page

    def load_data(self):
        f = self.search.text(); cur = self.db.conn.cursor()
        if f: cur.execute("SELECT id, nom, marque, sn, quantite, statut FROM equipement WHERE nom LIKE ? OR marque LIKE ?", (f'%{f}%', f'%{f}%'))
        else: cur.execute("SELECT id, nom, marque, sn, quantite, statut FROM equipement")
        rows = cur.fetchall(); self.table.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.table.insertRow(r_idx)
            for c_idx, d in enumerate(r_data):
                it = QTableWidgetItem(str(d)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c_idx == 5: it.setForeground(QColor("#00FF00") if d == "En stock" else QColor("#FF4444"))
                self.table.setItem(r_idx, c_idx, it)
            btn = QPushButton("Rentrer" if r_data[5]=="Sorti" else "Sortir")
            btn.clicked.connect(lambda ch, i=r_data[0]: self.toggle_item_status(i)); self.table.setCellWidget(r_idx, 6, btn)

    def toggle_item_status(self, i_id):
        cur = self.db.conn.cursor(); cur.execute("SELECT nom, statut, quantite, is_lot, sn, parent_id FROM equipement WHERE id = ?", (i_id,))
        res = cur.fetchone(); 
        if not res: return
        nom, st, qte, lot, sn, p_id = res; now = datetime.datetime.now().strftime("%d/%m %H:%M")
        if lot and st == "En stock" and qte > 1:
            val, ok = QInputDialog.getInt(self, "Sortie Lot", f"Sortir combien de '{nom}' ?", 1, 1, qte)
            if ok:
                if val == qte: cur.execute("UPDATE equipement SET statut='Sorti', date_sortie=? WHERE id=?", (now, i_id))
                else:
                    cur.execute("UPDATE equipement SET quantite=quantite-? WHERE id=?", (val, i_id))
                    cur.execute("INSERT INTO equipement (nom, marque, sn, quantite, is_lot, statut, parent_id, date_sortie) VALUES (?,?,?,?,?,?,?,?)",
                                (nom, "Générique", f"{sn}-OUT", val, 1, "Sorti", i_id, now))
        elif p_id and st == "Sorti":
            cur.execute("UPDATE equipement SET quantite=quantite+? WHERE id=?", (qte, p_id)); cur.execute("DELETE FROM equipement WHERE id=?", (i_id,))
        else:
            nv = "Sorti" if st=="En stock" else "En stock"
            cur.execute("UPDATE equipement SET statut=?, date_sortie=? WHERE id=?", (nv, now if nv=="Sorti" else None, i_id))
        self.db.conn.commit(); self.load_data(); self.load_check_data(); self.show_toast(f"{nom} mis à jour")

    def create_check_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,30,30,30); t = QLabel("Matériel Sorti"); t.setObjectName("TitleLabel")
        self.check_t = QTableWidget(); self.check_t.setColumnCount(5); self.check_t.setHorizontalHeaderLabels(["ID", "Nom", "Marque", "Qté", "Sorti le"])
        self.check_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.check_t.verticalHeader().setDefaultSectionSize(40)
        btn = QPushButton("Tout rentrer"); btn.clicked.connect(self.return_all); l.addWidget(t); l.addWidget(self.check_t); l.addWidget(btn); return p

    def load_check_data(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT id, nom, marque, quantite, date_sortie FROM equipement WHERE statut='Sorti'")
        rows = cur.fetchall(); self.check_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.check_t.insertRow(r_idx)
            for c_idx, d in enumerate(r_data): self.check_t.setItem(r_idx, c_idx, QTableWidgetItem(str(d)))

    def return_all(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT id, quantite, parent_id FROM equipement WHERE parent_id IS NOT NULL AND statut='Sorti'")
        for db_id, qte, p_id in cur.fetchall(): cur.execute("UPDATE equipement SET quantite=quantite+? WHERE id=?", (qte, p_id)); cur.execute("DELETE FROM equipement WHERE id=?", (db_id,))
        cur.execute("UPDATE equipement SET statut='En stock', date_sortie=NULL WHERE statut='Sorti'"); self.db.conn.commit(); self.load_data(); self.load_check_data(); self.show_toast("Reset global OK")

    def create_kits_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,30,30,30); h = QHBoxLayout(); t = QLabel("Kits"); t.setObjectName("TitleLabel")
        btn = QPushButton("+ Nouveau"); btn.setObjectName("ActionBtn"); btn.clicked.connect(self.create_new_kit); h.addWidget(t); h.addStretch(); h.addWidget(btn); l.addLayout(h)
        self.kits_t = QTableWidget(); self.kits_t.setColumnCount(4); self.kits_t.setHorizontalHeaderLabels(["ID", "Nom", "Objets", "Action"])
        self.kits_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.kits_t.verticalHeader().setDefaultSectionSize(45); l.addWidget(self.kits_t); return p

    def load_kits_data(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT k.id, k.nom_kit, COUNT(ki.id_equipement) FROM kits k LEFT JOIN kit_items ki ON k.id=ki.id_kit GROUP BY k.id")
        rows = cur.fetchall(); self.kits_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.kits_t.insertRow(r_idx); [self.kits_t.setItem(r_idx, c, QTableWidgetItem(str(d))) for c, d in enumerate(r_data)]
            btn = QPushButton("Bascule"); btn.clicked.connect(lambda ch, k=r_data[0]: self.toggle_kit(k)); self.kits_t.setCellWidget(r_idx, 3, btn)

    def toggle_kit(self, k_id):
        cur = self.db.conn.cursor(); cur.execute("SELECT statut FROM equipement WHERE id IN (SELECT id_equipement FROM kit_items WHERE id_kit=?) LIMIT 1", (k_id,))
        res = cur.fetchone()
        if res:
            nv = "Sorti" if res[0]=="En stock" else "En stock"; now = datetime.datetime.now().strftime("%d/%m %H:%M") if nv=="Sorti" else None
            cur.execute("UPDATE equipement SET statut=?, date_sortie=? WHERE id IN (SELECT id_equipement FROM kit_items WHERE id_kit=?)", (nv, now, k_id))
            self.db.conn.commit(); self.load_data(); self.load_check_data(); self.show_toast(f"Kit {nv.upper()}")

    def create_maintenance_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,30,30,30); t = QLabel("Maintenance"); t.setObjectName("TitleLabel")
        self.maint_t = QTableWidget(); self.maint_t.setColumnCount(5); self.maint_t.setHorizontalHeaderLabels(["Date", "Objet", "Description", "Coût", "Réparateur"])
        self.maint_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); l.addWidget(t); l.addWidget(self.maint_t); return p

    def load_maintenance_data(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT r.date_reparation, e.nom, r.description, r.cout, r.prestataire FROM reparations r JOIN equipement e ON r.id_equipement=e.id ORDER BY r.date_reparation DESC")
        rows = cur.fetchall(); self.maint_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.maint_t.insertRow(r_idx); [self.maint_t.setItem(r_idx, c, QTableWidgetItem(str(d))) for c, d in enumerate(r_data)]

    def open_repair_dialog(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel: return
        row = sel[0].row(); i_id, nom = self.table.item(row,0).text(), self.table.item(row,1).text()
        d = AddRepairDialog(nom, self)
        if d.exec():
            cur = self.db.conn.cursor(); cur.execute("INSERT INTO reparations (id_equipement, date_reparation, description, cout, prestataire) VALUES (?,?,?,?,?)",
                                                     (i_id, d.date.text(), d.desc.text(), d.cout.text(), d.prestataire.text()))
            self.db.conn.commit(); self.load_maintenance_data()

    def open_add_dialog(self):
        d = AddDeviceDialog(self)
        if d.exec():
            cur = self.db.conn.cursor(); cat, qty = d.cat.currentText(), d.quantite.value(); lot = 1 if d.is_batch.isChecked() else 0
            nom = f"Câble {d.prise_a.currentText()} > {d.prise_b.currentText()} ({d.longueur.text()})" if cat=="Câblage" else d.nom.text()
            if cat=="Câblage":
                cur.execute("SELECT id FROM equipement WHERE nom=? AND statut='En stock'", (nom,))
                ex = cur.fetchone()
                if ex: cur.execute("UPDATE equipement SET quantite=quantite+? WHERE id=?", (qty, ex[0])); self.db.conn.commit(); self.load_data(); return
            sn = d.sn.text() if not lot else f"LOT-{os.urandom(2).hex().upper()}"
            cur.execute("INSERT INTO equipement (nom, marque, sn, quantite, is_lot, statut) VALUES (?,?,?,?,?,?)", (nom, d.marque.text(), sn, qty, lot, "En stock"))
            it_id = cur.lastrowid; [LogicManager.generate_qr(it_id, sn) if not lot else None]
            self.db.conn.commit(); self.load_data(); self.show_toast("Ajout réussi")

    def create_new_kit(self):
        n, ok = QInputDialog.getText(self, "Nouveau Kit", "Nom :")
        if ok and n:
            cur = self.db.conn.cursor(); cur.execute("INSERT INTO kits (nom_kit) VALUES (?)", (n,)); k_id = cur.lastrowid
            cur.execute("SELECT id, nom, marque FROM equipement"); items = cur.fetchall(); sel = SelectItemsDialog(items, self)
            if sel.exec():
                [cur.execute("INSERT INTO kit_items (id_kit, id_equipement) VALUES (?,?)", (k_id, i)) for i in sel.get_selected_ids()]
                self.db.conn.commit(); self.load_kits_data()
            else: cur.db.conn.rollback()

    def export_qr_sheet(self):
        sel = self.table.selectionModel().selectedRows(); rows = [r.row() for r in sel] if sel else range(self.table.rowCount())
        f, _ = QFileDialog.getSaveFileName(self, "Planche QR", "planche.pdf", "PDF (*.pdf)")
        if not f: return
        c = canvas.Canvas(f, pagesize=A4); w, h, count = A4[0], A4[1], 0
        for r_idx in rows:
            i_id, nom, mrq = self.table.item(r_idx,0).text(), self.table.item(r_idx,1).text(), self.table.item(r_idx,2).text()
            qr = f"data/qrcodes/QR_{i_id}.png"
            if os.path.exists(qr):
                cx, cy = 1*cm + ((count%4)*5*cm), h - 4*cm - ((count//4)*5*cm)
                c.drawImage(qr, cx, cy, 3.5*cm, 3.5*cm); c.setFont("Helvetica-Bold", 8); c.drawCentredString(cx+1.75*cm, cy-0.3*cm, mrq)
                c.setFont("Helvetica", 7); c.drawCentredString(cx+1.75*cm, cy-0.7*cm, nom[:25]); count+=1
                if count>=20: c.showPage(); count=0
        c.save(); self.show_toast("PDF exporté")

if __name__ == "__main__":
    LogicManager.setup_folders()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())