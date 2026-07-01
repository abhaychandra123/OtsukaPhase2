import { AccountsIndex } from "@/components/account/accounts-index";

// The browse-everything account directory. Complements the Command Center's
// Context pane (focused daily work): this is the one-stop roll-up of every
// account and its deals.
export default function JuniorAccountsPage() {
  return <AccountsIndex role="junior" />;
}
