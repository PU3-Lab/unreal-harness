#pragma once

#include "Commandlets/Commandlet.h"
#include "StateTreeSnapshotCommandlet.generated.h"

UCLASS()
class UStateTreeSnapshotCommandlet : public UCommandlet
{
    GENERATED_BODY()
public:
    UStateTreeSnapshotCommandlet();
    virtual int32 Main(const FString& Params) override;

private:
    FString ParseAssetPath(const FString& Params) const;
    FString ParseOutPath(const FString& Params) const;
};
