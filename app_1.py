from flask import Flask, render_template, request, send_file, redirect, url_for, session
import pandas as pd
import os
import uuid

app = Flask(__name__)
app.secret_key = "tajni_kljuc_123"

# ==============================
# KORISNICI (MOŽEŠ DODAVATI JOŠ)
# ==============================
korisnici = {
    "admin": "admin123",
    "user1": "pass1",
    "user2": "pass2"
}

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)


# =====================================================
# FLEKSIBILNO UČITAVANJE TABLICE (RAZLIČITI NAZIVI KOLONA)
# =====================================================
def ucitaj_i_pripremi(file_path):
    df = pd.read_excel(file_path)

    # Normalizacija naziva stupaca
    df.columns = [c.strip().lower() for c in df.columns]

    # Moguća imena stupaca
    mapiranja = {
        "redni broj": ["redni broj", "rb", "rbr"],
        "ident": ["ident", "id", "sifra", "šifra"],
        "naziv": ["naziv", "naziv artikla", "artikal", "ime"],
        "kolicina": ["kolicina", "količina", "kol", "kom", "qty", "quantity"]
    }

    stvarna_imena = {}

    for standard, moguca in mapiranja.items():
        for col in df.columns:
            if col in moguca:
                stvarna_imena[standard] = col
                break

        if standard not in stvarna_imena:
            raise ValueError(f"Nedostaje stupac za: {standard}")

    df = df[[ 
        stvarna_imena["redni broj"],
        stvarna_imena["ident"],
        stvarna_imena["naziv"],
        stvarna_imena["kolicina"]
    ]]

    df.columns = ["redni broj", "ident", "naziv", "kolicina"]

    df["ident"] = df["ident"].astype(str).str.strip()
    df["naziv"] = df["naziv"].astype(str).str.strip()
    df["kolicina"] = pd.to_numeric(df["kolicina"], errors="coerce").fillna(0)

    return df


# ==============================
# LOGIN
# ==============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        password = request.form["password"]

        if user in korisnici and korisnici[user] == password:
            session["user"] = user
            return redirect(url_for("upload"))
        else:
            return render_template("login.html", error="Pogrešno korisničko ime ili lozinka")

    return render_template("login.html", error=None)


# ==============================
# UPLOAD I USPOREDBA
# ==============================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        prijenosnica = request.files["prijenosnica"]
        checklista = request.files["checklista"]

        if not prijenosnica or not checklista:
            return "Niste učitali obje datoteke!"

        uid = str(uuid.uuid4())
        file1_path = os.path.join(UPLOAD_FOLDER, uid + "_" + prijenosnica.filename)
        file2_path = os.path.join(UPLOAD_FOLDER, uid + "_" + checklista.filename)

        prijenosnica.save(file1_path)
        checklista.save(file2_path)

        df1 = ucitaj_i_pripremi(file1_path)
        df2 = ucitaj_i_pripremi(file2_path)

        # SPAJANJE PO IDENT + NAZIV
        rez = pd.merge(
            df1,
            df2,
            on=["ident", "naziv"],
            how="outer",
            suffixes=("_prijenos", "_check"),
            indicator=True
        )

        rez["kolicina_prijenos"] = rez["kolicina_prijenos"].fillna(0)
        rez["kolicina_check"] = rez["kolicina_check"].fillna(0)

        status = []

        for _, r in rez.iterrows():
            if r["_merge"] == "left_only":
                status.append("MANJAK")
            elif r["_merge"] == "right_only":
                status.append("VISAK")
            else:
                if r["kolicina_prijenos"] == r["kolicina_check"]:
                    status.append("OK")
                elif r["kolicina_prijenos"] > r["kolicina_check"]:
                    status.append("MANJAK")
                else:
                    status.append("VISAK")

        rez["STATUS"] = status
        rez["RAZLIKA"] = rez["kolicina_prijenos"] - rez["kolicina_check"]

        rezultat = rez[[
            "ident",
            "naziv",
            "kolicina_prijenos",
            "kolicina_check",
            "RAZLIKA",
            "STATUS"
        ]]

        rezultat.columns = [
            "IDENT",
            "NAZIV",
            "KOLIČINA PRIJENOSNICA",
            "KOLIČINA CHECK",
            "RAZLIKA",
            "STATUS"
        ]

        result_file = os.path.join(RESULT_FOLDER, f"rezultat_{uid}.xlsx")
        rezultat.to_excel(result_file, index=False)

        return send_file(result_file, as_attachment=True)

    return render_template("index.html")


# ==============================
# LOGOUT
# ==============================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ==============================
# POKRETANJE NA PORTU 8000
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
