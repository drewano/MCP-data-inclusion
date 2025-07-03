import { ChatWindow } from "@/components/chat";

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 p-4">
      <div className="container mx-auto py-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Assistant d&apos;Inclusion Sociale
          </h1>
          <p className="text-muted-foreground">
            Votre assistant IA pour découvrir les ressources et services d&apos;inclusion sociale en France
          </p>
        </div>
        <ChatWindow />
      </div>
    </main>
  );
}
