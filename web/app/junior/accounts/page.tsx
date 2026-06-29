import { redirect } from "next/navigation";

// The accounts list is now the Context pane (and account drawer) of the Junior
// Command Center at /junior. Individual accounts stay reachable at
// /junior/accounts/[id]; this index route redirects so old links don't 404.
export default function JuniorAccountsRedirect() {
  redirect("/junior");
}
