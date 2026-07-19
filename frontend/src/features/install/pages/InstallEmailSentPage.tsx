import { Link, useSearchParams } from "react-router-dom";

export default function InstallEmailSentPage() {
  const [searchParams] = useSearchParams();
  const email = (searchParams.get("email") || "").trim();
  const resent = searchParams.get("resent") === "1";
  const mode = (searchParams.get("mode") || "confirm").trim();
  const isConfirm = mode !== "password";

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/install" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a telepítő oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-lg w-full rounded border border-[var(--color-border)] bg-[var(--color-card)] p-6 md:p-8">
          <h1 className="text-2xl font-bold mb-4">
            {isConfirm ? "Elküldtük a megerősítő emailt" : "Elküldtük a jelszóbeállító linkedet emailben"}
          </h1>
          <p className="text-[var(--color-muted-foreground)] mb-3">
            {isConfirm
              ? resent
                ? "Új megerősítő linket küldtünk. Nyisd meg az emailben kapott linket, erősítsd meg a címedet, majd állítsd be a jelszavad."
                : "Nyisd meg az emailben kapott megerősítő linket. A megerősítés után létrehozzuk a környezetedet, és beállíthatod a jelszavad."
              : resent
                ? "Az új jelszóbeállító linket elküldtük. Nyisd meg az emailben kapott linket, állítsd be a jelszavadat, és már tesztelhetsz is."
                : "A környezeted elkészült. Nyisd meg az emailben kapott linket, állítsd be a jelszavadat, és már tesztelhetsz is."}
          </p>
          <p className="text-[var(--color-muted-foreground)] mb-3">
            Ha nem látod az üzenetet, ellenőrizd a spam/promóciók mappát is.
          </p>
          {email ? <p className="text-sm text-[var(--color-foreground)]">Kiküldve erre a címre: {email}</p> : null}
        </div>
      </main>
    </div>
  );
}
