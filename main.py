import sys
import os
import qrcode
import cv2
import datetime
import csv
import random
import string
from pyzbar.pyzbar import decode, ZBarSymbol
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QComboBox, 
                             QFileDialog, QMessageBox, QInputDialog, QListWidget, QListWidgetItem, QCheckBox, QSpinBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor, QFont
from database import Database

# Imports pour le PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# --- LOGIQUE METIER ---
class LogicManager:
    @staticmethod
    def setup_folders():
        for path in ["data/qrcodes", "data/factures"]:
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def generate_unique_sn(prefix="INT"):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}-{suffix}"

    @staticmethod
    def generate_qr(item_id, sn):
        if not sn: return None
        try:
            path = f"data/qrcodes/QR_{item_id}.png"
            img = qrcode.make(f"PROSTOCK-ID:{item_id}-SN:{sn}")
            img.save(path)
            return path
        except: return None

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
        layout.addLayout(form); self.btn_save = QPushButton("Envoyer en réparation"); self.btn_save.setObjectName("ActionBtn")
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
    def __init__(self, parent=None, edit_data=None):
        super().__init__(parent); self.setWindowTitle("Matériel"); self.setFixedWidth(500)
        layout = QVBoxLayout(self); self.form = QFormLayout()
        self.cat = QComboBox(); self.cat.addItems(["Photo", "Vidéo", "Son", "Câblage", "Accessoires"])
        self.cat.currentTextChanged.connect(self.toggle_cable_fields)
        self.nom = QLineEdit(); self.marque = QLineEdit(); self.sn = QLineEdit()
        self.prix = QLineEdit(); self.prix.setPlaceholderText("0.00")
        self.is_batch = QCheckBox("Gérer en quantité"); self.quantite = QSpinBox()
        self.quantite.setRange(1, 999); self.quantite.setEnabled(False)
        self.is_batch.toggled.connect(lambda c: self.quantite.setEnabled(c))
        
        self.cable_widget = QWidget(); self.cable_layout = QFormLayout(self.cable_widget)
        self.p_a = QComboBox(); self.p_a.addItems(["XLR M", "XLR F", "Jack 6.35", "RCA", "USB-C", "HDMI"]); self.p_a.setEditable(True)
        self.p_b = QComboBox(); self.p_b.addItems(["XLR F", "XLR M", "Jack 6.35", "RCA", "USB-C", "HDMI"]); self.p_b.setEditable(True)
        self.lg = QLineEdit(); self.lg.setPlaceholderText("ex: 5m")
        self.cable_layout.addRow("Prise A :", self.p_a); self.cable_layout.addRow("Prise B :", self.p_b); self.cable_layout.addRow("Longueur :", self.lg); self.cable_widget.hide()
        
        self.form.addRow("Catégorie :", self.cat); self.form.addRow(self.cable_widget); self.form.addRow("Nom :", self.nom)
        self.form.addRow("Marque :", self.marque); self.form.addRow("Lot ?", self.is_batch); self.form.addRow("Qté :", self.quantite)
        self.form.addRow("S/N :", self.sn); self.form.addRow("Prix (€) :", self.prix)
        layout.addLayout(self.form); self.btn_save = QPushButton("Enregistrer"); self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.accept); layout.addWidget(self.btn_save)

        if edit_data:
            self.cat.setCurrentText(edit_data['categorie']); self.nom.setText(edit_data['nom'])
            self.marque.setText(edit_data['marque']); self.sn.setText(edit_data['sn'])
            self.prix.setText(str(edit_data['prix'])); self.is_batch.setChecked(edit_data['is_lot'])
            self.quantite.setValue(edit_data['quantite'])

    def toggle_cable_fields(self, text):
        self.cable_widget.setVisible(text == "Câblage")

# --- FENÊTRE PRINCIPALE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.db = Database(); self.update_db_schema(); self.resize(1400, 850)
        main_widget = QWidget(); self.setCentralWidget(main_widget); self.main_layout = QHBoxLayout(main_widget)
        self.main_layout.setContentsMargins(0,0,0,0)

        # Sidebar
        self.sidebar = QWidget(); self.sidebar.setObjectName("Sidebar"); sidebar_layout = QVBoxLayout(self.sidebar)
        logo = QLabel("PRO-STOCK"); logo.setObjectName("TitleLabel"); sidebar_layout.addWidget(logo)
        self.btn_inv = QPushButton("📦 Inventaire"); self.btn_kits = QPushButton("🧰 Kits")
        self.btn_check = QPushButton("🔄 Check In/Out"); self.btn_maint = QPushButton("🛠 Maintenance")
        for b in [self.btn_inv, self.btn_kits, self.btn_check, self.btn_maint]: sidebar_layout.addWidget(b)
        sidebar_layout.addStretch()

        self.toast = QLabel(self); self.toast.setObjectName("Toast"); self.toast.hide()
        self.toast_timer = QTimer(); self.toast_timer.timeout.connect(self.toast.hide)

        # Content
        self.content = QStackedWidget()
        self.page_inv = self.create_inv_page()
        self.page_kits = self.create_kits_page()
        self.page_check = self.create_check_page()
        self.page_maint = self.create_maintenance_page()
        for p in [self.page_inv, self.page_kits, self.page_check, self.page_maint]: self.content.addWidget(p)
        self.main_layout.addWidget(self.sidebar); self.main_layout.addWidget(self.content)

        self.btn_inv.clicked.connect(lambda: self.content.setCurrentIndex(0))
        self.btn_kits.clicked.connect(lambda: self.content.setCurrentIndex(1))
        self.btn_check.clicked.connect(lambda: self.content.setCurrentIndex(2))
        self.btn_maint.clicked.connect(lambda: self.content.setCurrentIndex(3))

        self.refresh_all(); self.load_stylesheet()

    def update_db_schema(self):
        cursor = self.db.conn.cursor()
        for col in ["quantite INTEGER DEFAULT 1", "is_lot INTEGER DEFAULT 0", "parent_id INTEGER DEFAULT NULL", "date_sortie TEXT", "categorie TEXT", "prix REAL DEFAULT 0"]:
            try: cursor.execute(f"ALTER TABLE equipement ADD COLUMN {col}")
            except: pass
        self.db.conn.commit()

    def refresh_all(self):
        self.load_data(); self.load_check_data(); self.load_maintenance_data(); self.load_kits_data(); self.update_dashboard()

    def show_toast(self, message):
        self.toast.setText(message); self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2, self.height() - 80)
        self.toast.show(); self.toast_timer.start(2500)

    def create_stat_card(self, title, color):
        card = QFrame(); card.setObjectName("StatCard"); card.setStyleSheet(f"QFrame#StatCard {{ background-color: #1e1e1e; border-radius: 8px; border-left: 5px solid {color}; padding: 10px; }}")
        lay = QVBoxLayout(card); t = QLabel(title); t.setStyleSheet("color: #888; font-size: 11px;"); v = QLabel("0")
        v.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;"); lay.addWidget(t); lay.addWidget(v); card.v = v; return card

    def update_dashboard(self):
        cur = self.db.conn.cursor()
        cur.execute("SELECT SUM(prix * quantite) FROM equipement"); val = cur.fetchone()[0] or 0
        self.stat_val.v.setText(f"{val:,.2f} €")
        cur.execute("SELECT COUNT(*) FROM equipement WHERE statut = 'Sorti'"); out = cur.fetchone()[0] or 0
        self.stat_out.v.setText(str(out))
        cur.execute("SELECT COUNT(*) FROM equipement WHERE statut = 'En Maintenance'"); maint = cur.fetchone()[0] or 0
        self.stat_maint.v.setText(str(maint))

    def create_inv_page(self):
        p = QWidget(); l = QVBoxLayout(p); dash = QHBoxLayout()
        self.stat_val = self.create_stat_card("VALEUR PARC", "#3498db"); self.stat_out = self.create_stat_card("MATÉRIEL SORTI", "#e74c3c")
        self.stat_maint = self.create_stat_card("EN RÉPARATION", "#f39c12"); dash.addWidget(self.stat_val); dash.addWidget(self.stat_out); dash.addWidget(self.stat_maint)
        l.addLayout(dash); h = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Rechercher..."); self.search.textChanged.connect(self.load_data)
        btn_csv = QPushButton("📊 CSV"); btn_csv.clicked.connect(self.export_to_csv)
        btn_qr = QPushButton("🖨️ QR"); btn_qr.clicked.connect(self.export_qr_sheet)
        btn_add = QPushButton("+ Ajouter"); btn_add.setObjectName("ActionBtn"); btn_add.clicked.connect(self.open_add_dialog)
        h.addWidget(self.search); h.addStretch(); h.addWidget(btn_csv); h.addWidget(btn_qr); h.addWidget(btn_add)
        l.addLayout(h); self.table = QTableWidget(); self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(["ID", "Catégorie", "Nom", "Marque", "S/N", "Qté", "Statut", "Mouve.", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.table); return p

    def get_cat_color(self, cat):
        colors = {"Photo": "#3498db", "Vidéo": "#e74c3c", "Son": "#2ecc71", "Câblage": "#f39c12", "Accessoires": "#95a5a6"}
        return colors.get(cat, "#ffffff")

    def load_data(self):
        f = self.search.text(); cur = self.db.conn.cursor()
        q = "SELECT id, categorie, nom, marque, sn, quantite, statut, prix, is_lot FROM equipement"
        if f: cur.execute(f"{q} WHERE nom LIKE ? OR marque LIKE ? OR categorie LIKE ?", (f'%{f}%', f'%{f}%', f'%{f}%'))
        else: cur.execute(q)
        rows = cur.fetchall(); self.table.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.table.insertRow(r_idx)
            for c_idx in range(7):
                val = str(r_data[c_idx] if r_data[c_idx] else "---")
                it = QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # GESTION DES COULEURS
                if c_idx == 1: # Catégorie
                    it.setForeground(QColor(self.get_cat_color(val)))
                    f_bold = QFont(); f_bold.setBold(True); it.setFont(f_bold)
                
                if c_idx == 6: # Statut
                    color = "#00FF00" if r_data[c_idx] == "En stock" else "#FF4444"
                    if r_data[c_idx] == "En Maintenance": color = "#f39c12"
                    it.setForeground(QColor(color))
                    
                self.table.setItem(r_idx, c_idx, it)
            
            # Bouton Mouvement
            btn_mv = QPushButton("Rentrer" if r_data[6]=="Sorti" else "Sortir")
            if r_data[6] == "En Maintenance": btn_mv.setEnabled(False); btn_mv.setText("En Rép.")
            btn_mv.clicked.connect(lambda ch, i=r_data[0]: self.toggle_status(i)); self.table.setCellWidget(r_idx, 7, btn_mv)
            
            # Actions
            act_lay = QHBoxLayout(); w = QWidget()
            btn_e = QPushButton("✏️"); btn_e.setFixedWidth(30); btn_e.clicked.connect(lambda ch, d=r_data: self.edit_item(d))
            btn_m = QPushButton("🛠️"); btn_m.setFixedWidth(30); btn_m.setEnabled(r_data[6]=="En stock"); btn_m.clicked.connect(lambda ch, i=r_data[0], n=r_data[2]: self.open_repair_dialog(i, n))
            btn_d = QPushButton("🗑️"); btn_d.setFixedWidth(30); btn_d.clicked.connect(lambda ch, i=r_data[0]: self.delete_item(i))
            act_lay.addWidget(btn_e); act_lay.addWidget(btn_m); act_lay.addWidget(btn_d); act_lay.setContentsMargins(0,0,0,0)
            w.setLayout(act_lay); self.table.setCellWidget(r_idx, 8, w)
        self.update_dashboard()

    def edit_item(self, data):
        mapped = {'id': data[0], 'categorie': data[1], 'nom': data[2], 'marque': data[3], 'sn': data[4], 'quantite': data[5], 'prix': data[7], 'is_lot': data[8]}
        d = AddDeviceDialog(self, edit_data=mapped)
        if d.exec():
            cur = self.db.conn.cursor()
            cur.execute("UPDATE equipement SET nom=?, marque=?, sn=?, prix=?, quantite=?, categorie=?, is_lot=? WHERE id=?",
                        (d.nom.text(), d.marque.text(), d.sn.text(), float(d.prix.text() or 0), d.quantite.value(), d.cat.currentText(), 1 if d.is_batch.isChecked() else 0, mapped['id']))
            self.db.conn.commit(); self.refresh_all()

    def delete_item(self, i_id):
        if QMessageBox.question(self, "Supprimer", "Supprimer définitivement ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            cur = self.db.conn.cursor(); cur.execute("DELETE FROM equipement WHERE id=?", (i_id,)); self.db.conn.commit(); self.refresh_all()

    def toggle_status(self, i_id):
        cur = self.db.conn.cursor(); cur.execute("SELECT nom, statut, quantite, is_lot, parent_id FROM equipement WHERE id = ?", (i_id,))
        res = cur.fetchone(); 
        if not res: return
        nom, st, qte, lot, p_id = res; now = datetime.datetime.now().strftime("%d/%m %H:%M")
        if lot and st == "En stock" and qte > 1:
            val, ok = QInputDialog.getInt(self, "Sortie", f"Qté pour '{nom}' ?", 1, 1, qte)
            if ok:
                if val == qte: cur.execute("UPDATE equipement SET statut='Sorti', date_sortie=? WHERE id=?", (now, i_id))
                else:
                    cur.execute("UPDATE equipement SET quantite=quantite-? WHERE id=?", (val, i_id))
                    cur.execute("INSERT INTO equipement (nom, marque, sn, quantite, is_lot, statut, parent_id, date_sortie, categorie) SELECT nom, marque, 'LOT-OUT', ?, 1, 'Sorti', ?, ?, categorie FROM equipement WHERE id=?", (val, i_id, now, i_id))
        elif p_id and st == "Sorti":
            cur.execute("UPDATE equipement SET quantite=quantite+? WHERE id=?", (qte, p_id)); cur.execute("DELETE FROM equipement WHERE id=?", (i_id,))
        else:
            nv = "Sorti" if st=="En stock" else "En stock"
            cur.execute("UPDATE equipement SET statut=?, date_sortie=? WHERE id=?", (nv, now if nv=="Sorti" else None, i_id))
        self.db.conn.commit(); self.refresh_all()

    def create_check_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.addWidget(QLabel("MATÉRIEL SORTI"))
        self.check_t = QTableWidget(); self.check_t.setColumnCount(5)
        self.check_t.setHorizontalHeaderLabels(["ID", "Nom", "Marque", "Qté", "Sorti le"])
        self.check_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.check_t); return p

    def load_check_data(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT id, nom, marque, quantite, date_sortie FROM equipement WHERE statut='Sorti'")
        rows = cur.fetchall(); self.check_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.check_t.insertRow(r_idx); [self.check_t.setItem(r_idx, c, QTableWidgetItem(str(d))) for c, d in enumerate(r_data)]

    def create_maintenance_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,30,30,30); l.addWidget(QLabel("MATÉRIEL EN RÉPARATION"))
        self.maint_t = QTableWidget(); self.maint_t.setColumnCount(6)
        self.maint_t.setHorizontalHeaderLabels(["ID", "Date", "Objet", "Panne", "Coût", "Action"])
        self.maint_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.maint_t); return p

    def load_maintenance_data(self):
        cur = self.db.conn.cursor()
        cur.execute("SELECT r.id, r.date_reparation, e.nom, r.description, r.cout, e.id FROM reparations r JOIN equipement e ON r.id_equipement=e.id WHERE e.statut='En Maintenance'")
        rows = cur.fetchall(); self.maint_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.maint_t.insertRow(r_idx)
            for c_idx in range(5): self.maint_t.setItem(r_idx, c_idx, QTableWidgetItem(str(r_data[c_idx])))
            btn = QPushButton("✅ Terminer"); btn.clicked.connect(lambda ch, i=r_data[5]: self.finish_repair(i))
            self.maint_t.setCellWidget(r_idx, 5, btn)

    def open_repair_dialog(self, i_id, nom):
        d = AddRepairDialog(nom, self)
        if d.exec():
            cur = self.db.conn.cursor()
            cur.execute("INSERT INTO reparations (id_equipement, date_reparation, description, cout, prestataire) VALUES (?,?,?,?,?)",
                        (i_id, d.date.text(), d.desc.text(), d.cout.text(), d.prestataire.text()))
            cur.execute("UPDATE equipement SET statut='En Maintenance' WHERE id=?", (i_id,))
            self.db.conn.commit(); self.refresh_all(); self.show_toast("Matériel envoyé en SAV")

    def finish_repair(self, i_id):
        cur = self.db.conn.cursor(); cur.execute("UPDATE equipement SET statut='En stock' WHERE id=?", (i_id,))
        self.db.conn.commit(); self.refresh_all(); self.show_toast("Matériel de retour en stock")

    def open_add_dialog(self):
        d = AddDeviceDialog(self)
        if d.exec():
            cur = self.db.conn.cursor(); cat = d.cat.currentText(); qty = d.quantite.value(); lot = 1 if d.is_batch.isChecked() else 0
            nom = f"Câble {d.p_a.currentText()} > {d.p_b.currentText()} ({d.lg.text()})" if cat=="Câblage" else d.nom.text()
            sn = d.sn.text().strip() or LogicManager.generate_unique_sn(cat[:4].upper())
            cur.execute("INSERT INTO equipement (nom, marque, sn, quantite, is_lot, statut, categorie, prix) VALUES (?,?,?,?,?,?,?,?)",
                        (nom, d.marque.text(), sn, qty, lot, "En stock", cat, float(d.prix.text() or 0)))
            if not lot: LogicManager.generate_qr(cur.lastrowid, sn)
            self.db.conn.commit(); self.refresh_all(); self.show_toast("Ajouté")

    def create_kits_page(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,30,30,30); h = QHBoxLayout(); t = QLabel("GESTION DES KITS")
        btn = QPushButton("+ NOUVEAU KIT"); btn.clicked.connect(self.create_new_kit)
        h.addWidget(t); h.addStretch(); h.addWidget(btn); l.addLayout(h)
        self.kits_t = QTableWidget(); self.kits_t.setColumnCount(4); self.kits_t.setHorizontalHeaderLabels(["ID", "Nom du Kit", "Objets", "Action"])
        self.kits_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); l.addWidget(self.kits_t); return p

    def load_kits_data(self):
        cur = self.db.conn.cursor(); cur.execute("SELECT k.id, k.nom_kit, COUNT(ki.id_equipement) FROM kits k LEFT JOIN kit_items ki ON k.id=ki.id_kit GROUP BY k.id")
        rows = cur.fetchall(); self.kits_t.setRowCount(0)
        for r_idx, r_data in enumerate(rows):
            self.kits_t.insertRow(r_idx); [self.kits_t.setItem(r_idx, c, QTableWidgetItem(str(d))) for c, d in enumerate(r_data)]
            btn = QPushButton("Basculer Statut"); btn.clicked.connect(lambda ch, k=r_data[0]: self.toggle_kit(k)); self.kits_t.setCellWidget(r_idx, 3, btn)

    def toggle_kit(self, k_id):
        cur = self.db.conn.cursor(); cur.execute("SELECT statut FROM equipement WHERE id IN (SELECT id_equipement FROM kit_items WHERE id_kit=?) LIMIT 1", (k_id,))
        res = cur.fetchone(); 
        if res:
            nv = "Sorti" if res[0]=="En stock" else "En stock"; now = datetime.datetime.now().strftime("%d/%m %H:%M") if nv=="Sorti" else None
            cur.execute("UPDATE equipement SET statut=?, date_sortie=? WHERE id IN (SELECT id_equipement FROM kit_items WHERE id_kit=?)", (nv, now, k_id))
            self.db.conn.commit(); self.refresh_all(); self.show_toast(f"Kit {nv}")

    def create_new_kit(self):
        n, ok = QInputDialog.getText(self, "Nouveau Kit", "Nom :")
        if ok and n:
            cur = self.db.conn.cursor(); cur.execute("INSERT INTO kits (nom_kit) VALUES (?)", (n,)); k_id = cur.lastrowid
            cur.execute("SELECT id, nom, marque FROM equipement"); items = cur.fetchall(); sel = SelectItemsDialog(items, self)
            if sel.exec():
                [cur.execute("INSERT INTO kit_items (id_kit, id_equipement) VALUES (?,?)", (k_id, i)) for i in sel.get_selected_ids()]
                self.db.conn.commit(); self.load_kits_data(); self.show_toast("Kit créé")

    def export_qr_sheet(self):
        sel = self.table.selectionModel().selectedRows(); rows = [r.row() for r in sel] if sel else range(self.table.rowCount())
        f, _ = QFileDialog.getSaveFileName(self, "Planche QR", "planche.pdf", "PDF (*.pdf)")
        if f:
            c = canvas.Canvas(f, pagesize=A4); h, count = A4[1], 0
            for r_idx in rows:
                i_id, nom, mrq = self.table.item(r_idx,0).text(), self.table.item(r_idx,2).text(), self.table.item(r_idx,3).text()
                qr = f"data/qrcodes/QR_{i_id}.png"
                if os.path.exists(qr):
                    cx, cy = 1*cm + ((count%4)*5*cm), h - 4*cm - ((count//4)*5*cm)
                    c.drawImage(qr, cx, cy, 3.5*cm, 3.5*cm); c.setFont("Helvetica-Bold", 8); c.drawCentredString(cx+1.75*cm, cy-0.3*cm, mrq)
                    c.setFont("Helvetica", 7); c.drawCentredString(cx+1.75*cm, cy-0.7*cm, nom[:25]); count+=1
                    if count>=20: c.showPage(); count=0
            c.save(); self.show_toast("PDF exporté")

    def export_to_csv(self):
        f, _ = QFileDialog.getSaveFileName(self, "Export", "inventaire.csv", "CSV (*.csv)")
        if f:
            cur = self.db.conn.cursor(); cur.execute("SELECT id, categorie, nom, marque, sn, quantite, statut, date_sortie FROM equipement")
            with open(f, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file, delimiter=';'); writer.writerow(["ID", "Cat", "Nom", "Marque", "S/N", "Qté", "Statut", "Sorti"])
                writer.writerows(cur.fetchall())
            self.show_toast("CSV Exporté")

    def load_stylesheet(self):
        if os.path.exists("styles.qss"):
            with open("styles.qss", "r") as f: self.setStyleSheet(f.read())

if __name__ == "__main__":
    LogicManager.setup_folders(); app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec())