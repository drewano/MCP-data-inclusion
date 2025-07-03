import Image from "next/image";

export default function Home() {
  return (
    <main className="flex items-center justify-center min-h-screen p-4">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-foreground">
          Assistant d&apos;Inclusion Sociale
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl">
          Votre assistant IA pour découvrir les ressources et services d&apos;inclusion sociale en France
        </p>
      </div>
    </main>
  );
}
