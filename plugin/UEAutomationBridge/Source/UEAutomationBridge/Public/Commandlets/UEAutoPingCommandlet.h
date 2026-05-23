#pragma once

#include "Commandlets/Commandlet.h"
#include "UEAutoPingCommandlet.generated.h"

UCLASS()
class UUEAutoPingCommandlet : public UCommandlet
{
    GENERATED_BODY()
public:
    UUEAutoPingCommandlet();
    virtual int32 Main(const FString& Params) override;
};
