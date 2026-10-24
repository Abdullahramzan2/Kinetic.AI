import "./App.css";
import { useState } from "react";
import { useMantineTheme } from "@mantine/core";
import Header from "./components/Header";
import InitialInput from "./components/InitialInput";
import ChatPanel from "./components/chat/ChatPanel";
import WorkspacePanel from "./components/workspace/WorkspacePanel";

function Home() {
  const theme = useMantineTheme();
  const [messages, setMessages] = useState([]);
  const [currentPrompt, setCurrentPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [workspaceContent, setWorkspaceContent] = useState([]);
  const [conversationId, setConversationId] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (currentPrompt.trim() && !loading) {
      const userMessage = { text: currentPrompt, type: "user", id: Date.now() };
      setMessages((prev) => [...prev, userMessage]);
      const promptToSend = currentPrompt;
      setCurrentPrompt("");
      setLoading(true);

      try {
        const token = localStorage.getItem("token");
        if (!token) {
          throw new Error("Please log in first");
        }

        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        };

        const response = await fetch(
          `${process.env.REACT_APP_APP_URL}/model/generate`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              prompt: promptToSend,
              model: "local",
              conversation_id: conversationId || undefined,
            }),
          }
        );

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new Error(errBody.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.conversation_id && !conversationId) {
          setConversationId(data.conversation_id);
        }

        setWorkspaceContent((prev) => [...prev, data]);

        // Show missing_info / errors in the chat as well
        const plan = data.response;
        if (plan && (plan.missing_info || plan.error)) {
          setMessages((prev) => [
            ...prev,
            {
              text: plan.missing_info || plan.error,
              type: "bot",
              id: Date.now() + 1,
            },
          ]);
        }
      } catch (error) {
        const errorMessage = {
          text: `Error: ${error.message || "Network issue - please try again"}`,
          type: "bot",
          id: Date.now() + 1,
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: theme.other.background,
        overflow: "hidden",
        paddingTop: "80px", // Account for fixed header
      }}>
      <Header />

      {messages.length === 0 ? (
        <InitialInput
          currentPrompt={currentPrompt}
          setCurrentPrompt={setCurrentPrompt}
          handleSubmit={handleSubmit}
          loading={loading}
        />
      ) : (
        <div
          style={{
            flex: 1,
            display: "flex",
            padding: "0 20px 20px 20px",
            gap: "20px",
            minHeight: 0,
          }}>
          <ChatPanel
            messages={messages}
            currentPrompt={currentPrompt}
            setCurrentPrompt={setCurrentPrompt}
            handleSubmit={handleSubmit}
            loading={loading}
          />
          <WorkspacePanel workspaceContent={workspaceContent} />
        </div>
      )}
    </div>
  );
}

export default Home;
