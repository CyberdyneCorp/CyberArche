# document-model Specification

## MODIFIED Requirements
### Requirement: Documents may belong to a teamspace
A document SHALL optionally reference a teamspace it belongs to, and SHALL
optionally reference a folder that groups it. A document with no teamspace is
private to its creator. Placing a document in a folder SHALL set the document's
teamspace to the folder's, so its access follows the container; moving a document
directly to a teamspace SHALL set its teamspace and clear any folder reference;
removing it to the private space SHALL clear its teamspace. Listing a workspace
SHALL surface a teamspace's documents to that teamspace's members, and a private
document only to its creator.

#### Scenario: A workspace lists teamspace documents to members
- **WHEN** a member lists a teamspace's documents
- **THEN** the documents belonging to that teamspace SHALL be returned

#### Scenario: Private documents are listed only to their creator
- **WHEN** a user lists their private documents
- **THEN** only their own teamspace-less documents SHALL be returned

#### Scenario: Placing a document in a folder adopts the folder's scope
- **WHEN** a document is placed in a folder that belongs to a teamspace
- **THEN** the document SHALL belong to that teamspace

#### Scenario: Moving a document directly to a teamspace clears its folder
- **GIVEN** a document that lives in a folder
- **WHEN** an editor moves the document to a teamspace
- **THEN** the document SHALL belong to that teamspace
- **AND** the document SHALL no longer reference any folder

#### Scenario: Moving a foldered document to the private space clears its teamspace
- **GIVEN** a document that lives in a folder within a teamspace
- **WHEN** the document is moved to the private space
- **THEN** the document SHALL have no teamspace and no folder
- **AND** it SHALL be listed only to its creator
